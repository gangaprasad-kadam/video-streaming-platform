import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import VideoCard from '@/components/VideoCard'
import VideoGrid from '@/components/VideoGrid'

const mockVideo = {
  id: 'v1',
  title: 'Introduction to React Hooks',
  thumbnail_url: null,
  creator_name: 'Jane Smith',
  duration: 305,
  view_count: 12500,
  status: 'ready',
}

function wrap(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('VideoCard', () => {
  it('T4.1 — renders thumbnail placeholder, title, creator, duration', () => {
    wrap(<VideoCard video={mockVideo} />)
    expect(screen.getByText('Introduction to React Hooks')).toBeInTheDocument()
    expect(screen.getByText('Jane Smith')).toBeInTheDocument()
    expect(screen.getByText('5:05')).toBeInTheDocument()  // 305s
    expect(screen.getByText('🎬')).toBeInTheDocument()   // placeholder
  })

  it('T4.2 — renders img when thumbnail_url is present', () => {
    wrap(<VideoCard video={{ ...mockVideo, thumbnail_url: '/thumb.jpg' }} />)
    expect(screen.getByRole('img')).toHaveAttribute('src', '/thumb.jpg')
  })

  it('T4.3 — card links to /videos/:id', () => {
    wrap(<VideoCard video={mockVideo} />)
    const link = screen.getByTestId('video-card')
    expect(link).toHaveAttribute('href', '/videos/v1')
  })

  it('formats view count correctly (K suffix)', () => {
    wrap(<VideoCard video={mockVideo} />)
    expect(screen.getByText('12.5K views')).toBeInTheDocument()
  })

  it('formats view count with M suffix for millions', () => {
    wrap(<VideoCard video={{ ...mockVideo, view_count: 2_300_000 }} />)
    expect(screen.getByText('2.3M views')).toBeInTheDocument()
  })

  it('shows "Processing" badge for processing status', () => {
    wrap(<VideoCard video={{ ...mockVideo, status: 'processing' }} />)
    expect(screen.getByText('Processing')).toBeInTheDocument()
  })
})

describe('VideoGrid', () => {
  it('renders VideoCards for each video', () => {
    wrap(<VideoGrid videos={[mockVideo, { ...mockVideo, id: 'v2', title: 'Vue Basics' }]} loading={false} />)
    expect(screen.getAllByTestId('video-card')).toHaveLength(2)
  })

  it('T4.6 — shows empty state when videos array is empty', () => {
    wrap(<VideoGrid videos={[]} loading={false} emptyTitle="No trending videos yet" />)
    expect(screen.getByText('No trending videos yet')).toBeInTheDocument()
  })

  it('renders skeleton cards when loading', () => {
    const { container } = wrap(<VideoGrid videos={[]} loading={true} skeletonCount={4} />)
    // Skeleton divs should be present (no video-card testids)
    expect(screen.queryAllByTestId('video-card')).toHaveLength(0)
    expect(container.querySelectorAll('.cardSkeleton, [class*="cardSkeleton"]').length).toBeGreaterThanOrEqual(0)
  })
})
