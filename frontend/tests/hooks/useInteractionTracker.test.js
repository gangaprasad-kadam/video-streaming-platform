import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import useInteractionTracker from '@/hooks/useInteractionTracker'

vi.mock('@/api/events', () => ({
  postInteraction: vi.fn().mockResolvedValue(undefined),
}))
import { postInteraction } from '@/api/events'

describe('useInteractionTracker', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.clearAllMocks() })
  afterEach(()  => { vi.useRealTimers() })

  it('T5.5 — events accumulate in buffer within 3s window', () => {
    const { result } = renderHook(() => useInteractionTracker('v1'))
    act(() => {
      // Simulate play event
      result.current.onPlay({ target: { currentTime: 0 } })
      result.current.onPlay({ target: { currentTime: 5 } })
    })
    expect(postInteraction).not.toHaveBeenCalled()
  })

  it('T5.6 — buffer flushes after 3s interval', async () => {
    const { result } = renderHook(() => useInteractionTracker('v1'))
    act(() => {
      result.current.onPlay({ target: { currentTime: 0 } })
    })
    await act(async () => { vi.advanceTimersByTime(3001) })
    expect(postInteraction).toHaveBeenCalledWith(
      expect.objectContaining({ videoId: 'v1', action: 'PLAY' })
    )
  })

  it('T5.8 — SEEK backward classified as REWIND', () => {
    const { result } = renderHook(() => useInteractionTracker('v1'))
    act(() => {
      // Set prev time to 30s
      result.current.onTimeUpdate({ target: { currentTime: 30 } })
      // Seek to 10s — backward
      result.current.onSeeked({ target: { currentTime: 10 } })
    })
    act(() => { vi.advanceTimersByTime(3001) })
    expect(postInteraction).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'REWIND', videoTs: 10 })
    )
  })

  it('T5.9 — SEEK forward classified as SEEK', () => {
    const { result } = renderHook(() => useInteractionTracker('v1'))
    act(() => {
      result.current.onTimeUpdate({ target: { currentTime: 10 } })
      result.current.onSeeked({ target: { currentTime: 40 } })
    })
    act(() => { vi.advanceTimersByTime(3001) })
    expect(postInteraction).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'SEEK', videoTs: 40 })
    )
  })

  it('T5.10 — on unmount, pending buffer is flushed', () => {
    const { result, unmount } = renderHook(() => useInteractionTracker('v1'))
    act(() => {
      result.current.onPause({ target: { currentTime: 15 } })
    })
    unmount()
    expect(postInteraction).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'PAUSE' })
    )
  })
})
