import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getHeatmap, getHighlights } from '@/api/heatmap'
import useHeatmapSSE from '@/hooks/useHeatmapSSE'
import s from './HeatmapChart.module.css'

// Maps a score (0-max) to a color from cool blue → warm red
function heatColor(score, max) {
  if (!max) return '#3b82f6'
  const ratio = score / max
  if (ratio < 0.33) return '#3b82f6'   // cold — blue
  if (ratio < 0.66) return '#f59e0b'   // warm — amber
  return '#ef4444'                      // hot  — red
}

function fmtTs(seg, bucketSize = 5) {
  const s = seg * bucketSize
  const m = Math.floor(s / 60)
  const ss = String(s % 60).padStart(2, '0')
  return `${m}:${ss}`
}

export default function HeatmapChart({ videoId, onSeek }) {
  const [segments,   setSegments]   = useState([])
  const [highlights, setHighlights] = useState([])
  const [loading,    setLoading]    = useState(true)
  const { data: liveData } = useHeatmapSSE(videoId)

  useEffect(() => {
    if (!videoId) return
    Promise.all([
      getHeatmap(videoId).catch(() => null),
      getHighlights(videoId).catch(() => []),
    ]).then(([heatmap, hi]) => {
      if (heatmap?.segments) setSegments(heatmap.segments)
      if (hi) setHighlights(Array.isArray(hi) ? hi : hi.highlights ?? [])
    }).finally(() => setLoading(false))
  }, [videoId])

  // Merge live SSE updates over all-time data
  useEffect(() => {
    if (!liveData?.segments) return
    setSegments((prev) => {
      const updated = [...prev]
      liveData.segments.forEach(({ segment_id, count }) => {
        const idx = updated.findIndex((x) => x.segment_id === segment_id)
        if (idx >= 0) updated[idx] = { ...updated[idx], count: (updated[idx].count || 0) + count }
        else updated.push({ segment_id, count })
      })
      return updated
    })
  }, [liveData])

  if (loading) return <div className={s.empty}><span className="spinner" /></div>
  if (!segments.length) return <div className={s.empty}>No heatmap data yet.</div>

  const max = Math.max(...segments.map((x) => x.count || 0), 1)
  const chartData = segments.map((x) => ({ ...x, name: fmtTs(x.segment_id) }))

  return (
    <div className={s.chart}>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={chartData} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 9 }} />
          <Tooltip
            formatter={(v) => [`${v} views`, 'Engagement']}
            contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 6, fontSize: 12 }}
          />
          <Bar
            dataKey="count"
            radius={[2, 2, 0, 0]}
            cursor="pointer"
            onClick={(entry) => onSeek?.(entry.segment_id * 5)}
          >
            {chartData.map((entry) => (
              <Cell key={entry.segment_id} fill={heatColor(entry.count, max)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {highlights.length > 0 && (
        <div className={s.highlightList}>
          <div className={s.highlightTitle}>🏆 Top rewatched segments</div>
          {highlights.slice(0, 5).map((h, i) => (
            <button
              key={i}
              className={s.highlight}
              onClick={() => onSeek?.(h.segment_id * 5)}
              data-testid="highlight-item"
            >
              <span className={s.rank}>#{i + 1}</span>
              <span>Segment at </span>
              <span className={s.ts}>{fmtTs(h.segment_id)}</span>
              <span> — {h.count} views</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
