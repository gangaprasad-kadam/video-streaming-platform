import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import useHeatmapSSE from '@/hooks/useHeatmapSSE'
import HeatmapChart from '@/components/HeatmapChart'

vi.mock('@/api/heatmap', () => ({
  getHeatmap:          vi.fn(),
  getHighlights:       vi.fn(),
  getHeatmapStreamUrl: (id) => `/heatmap/${id}/stream`,
}))

import { getHeatmap, getHighlights } from '@/api/heatmap'

// ── Shared EventSource mock factory ────────────────────────────────────────
let lastES
function makeESMock() {
  lastES = { onmessage: null, onerror: null, close: vi.fn() }
  class MockEventSource {
    constructor(url, opts) {
      this.url  = url
      this.opts = opts
      Object.assign(this, lastES)
      lastES = this
    }
  }
  return MockEventSource
}

// ── SSE hook tests ─────────────────────────────────────────────────────────
describe('useHeatmapSSE', () => {
  beforeEach(() => {
    global.EventSource = makeESMock()
    vi.clearAllMocks()
  })

  it('T8.1 — opens EventSource connection on mount', () => {
    renderHook(() => useHeatmapSSE('v1'))
    expect(lastES.url).toBe('/heatmap/v1/stream')
  })

  it('T8.2 — updates heatmapData when SSE message arrives', () => {
    const { result } = renderHook(() => useHeatmapSSE('v1'))
    act(() => {
      lastES.onmessage({ data: JSON.stringify({ segments: [{ segment_id: 0, count: 5 }] }) })
    })
    expect(result.current.data).toEqual({ segments: [{ segment_id: 0, count: 5 }] })
  })

  it('T8.3 — closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useHeatmapSSE('v1'))
    const es = lastES
    unmount()
    expect(es.close).toHaveBeenCalled()
  })
})

// ── HeatmapChart component tests ───────────────────────────────────────────
describe('HeatmapChart', () => {
  beforeEach(() => {
    global.EventSource = makeESMock()
    vi.clearAllMocks()
  })

  it('T8.5 — renders empty state when no segments', async () => {
    getHeatmap.mockResolvedValue({ segments: [] })
    getHighlights.mockResolvedValue([])
    render(<MemoryRouter><HeatmapChart videoId="v1" /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText(/no heatmap data/i)).toBeInTheDocument())
  })

  it('T8.8 — clicking a highlight calls onSeek with segment time', async () => {
    getHeatmap.mockResolvedValue({ segments: [{ segment_id: 3, count: 10 }] })
    getHighlights.mockResolvedValue([{ segment_id: 3, count: 10 }])
    const onSeek = vi.fn()
    render(<MemoryRouter><HeatmapChart videoId="v1" onSeek={onSeek} /></MemoryRouter>)
    await waitFor(() => screen.getByTestId('highlight-item'))
    await userEvent.click(screen.getByTestId('highlight-item'))
    expect(onSeek).toHaveBeenCalledWith(15)  // segment 3 × 5s = 15s
  })
})
