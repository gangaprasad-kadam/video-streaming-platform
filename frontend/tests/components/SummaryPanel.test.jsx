import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import SummaryPanel from '@/components/SummaryPanel'

vi.mock('@/api/summary', () => ({
  getSummary: vi.fn(),
}))
import { getSummary } from '@/api/summary'

const mockSummary = {
  summary: 'This is an AI-generated summary of the video.',
  transcript: 'Hello and welcome to this video...',
  key_moments: [
    { timestamp: 30,  label: 'Introduction' },
    { timestamp: 120, label: 'Main concept explained' },
  ],
}

describe('SummaryPanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('T7.1 — fetches GET /summary/:videoId on mount', () => {
    getSummary.mockResolvedValue(mockSummary)
    render(<MemoryRouter><SummaryPanel videoId="v1" /></MemoryRouter>)
    expect(getSummary).toHaveBeenCalledWith('v1')
  })

  it('T7.2 — renders summary text when data loads', async () => {
    getSummary.mockResolvedValue(mockSummary)
    render(<MemoryRouter><SummaryPanel videoId="v1" /></MemoryRouter>)
    await waitFor(() =>
      expect(screen.getByText('This is an AI-generated summary of the video.')).toBeInTheDocument()
    )
  })

  it('T7.3 — shows loading spinner while fetching', () => {
    getSummary.mockImplementation(() => new Promise(() => {}))
    render(<MemoryRouter><SummaryPanel videoId="v1" /></MemoryRouter>)
    expect(screen.getByText(/generating summary/i)).toBeInTheDocument()
  })

  it('T7.4 — shows "Summary not available" when 404', async () => {
    getSummary.mockRejectedValue(new Error('404 not found'))
    render(<MemoryRouter><SummaryPanel videoId="v1" /></MemoryRouter>)
    await waitFor(() =>
      expect(screen.getByText(/summary not available/i)).toBeInTheDocument()
    )
  })

  it('T7.5 — key moments list renders timestamp + label', async () => {
    getSummary.mockResolvedValue(mockSummary)
    render(<MemoryRouter><SummaryPanel videoId="v1" /></MemoryRouter>)
    await waitFor(() => screen.getByText('Introduction'))
    expect(screen.getByText('Main concept explained')).toBeInTheDocument()
    expect(screen.getByText('0:30')).toBeInTheDocument()
    expect(screen.getByText('2:00')).toBeInTheDocument()
  })

  it('T7.6 — clicking a key moment calls onSeek with timestamp', async () => {
    getSummary.mockResolvedValue(mockSummary)
    const onSeek = vi.fn()
    render(<MemoryRouter><SummaryPanel videoId="v1" onSeek={onSeek} /></MemoryRouter>)
    await waitFor(() => screen.getByText('Introduction'))
    await userEvent.click(screen.getByText('Introduction').closest('button'))
    expect(onSeek).toHaveBeenCalledWith(30)
  })

  it('T7.7 — transcript section toggles on click', async () => {
    getSummary.mockResolvedValue(mockSummary)
    render(<MemoryRouter><SummaryPanel videoId="v1" /></MemoryRouter>)
    await waitFor(() => screen.getByText(/show transcript/i))
    await userEvent.click(screen.getByText(/show transcript/i))
    expect(screen.getByText(/hello and welcome/i)).toBeInTheDocument()
    await userEvent.click(screen.getByText(/hide transcript/i))
    expect(screen.queryByText(/hello and welcome/i)).not.toBeInTheDocument()
  })
})
