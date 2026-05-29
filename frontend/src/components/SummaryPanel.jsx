import { useState, useEffect } from 'react'
import { getSummary } from '@/api/summary'
import s from './SummaryPanel.module.css'

function fmtTs(seconds) {
  const m = Math.floor(seconds / 60)
  const ss = String(Math.floor(seconds % 60)).padStart(2, '0')
  return `${m}:${ss}`
}

export default function SummaryPanel({ videoId, onSeek }) {
  const [data,         setData]         = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [notFound,     setNotFound]     = useState(false)
  const [showTranscript, setShowTranscript] = useState(false)

  useEffect(() => {
    if (!videoId) return
    setLoading(true)
    getSummary(videoId)
      .then(setData)
      .catch((e) => {
        if (e.message?.includes('404') || e.message?.toLowerCase().includes('not found')) {
          setNotFound(true)
        }
      })
      .finally(() => setLoading(false))
  }, [videoId])

  if (loading) return (
    <div className={s.loading}><span className="spinner" /> Generating summary…</div>
  )

  if (notFound || !data) return (
    <div className={s.empty}>
      <div className={s.emptyIcon}>🤖</div>
      Summary not available yet.<br />Check back after processing completes.
    </div>
  )

  return (
    <div className={s.panel}>
      {data.summary && <p className={s.summary}>{data.summary}</p>}

      {data.key_moments?.length > 0 && (
        <div>
          <div className={s.momentsTitle}>Key moments</div>
          <div className={s.moments}>
            {data.key_moments.map((m, i) => (
              <button
                key={i}
                className={s.moment}
                onClick={() => onSeek?.(m.timestamp)}
                aria-label={`Jump to ${fmtTs(m.timestamp)}: ${m.label}`}
              >
                <span className={s.momentTs}>{fmtTs(m.timestamp)}</span>
                <span className={s.momentLabel}>{m.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {data.transcript && (
        <>
          <button
            className={s.transcriptToggle}
            onClick={() => setShowTranscript((v) => !v)}
            aria-expanded={showTranscript}
          >
            {showTranscript ? '▲' : '▼'} {showTranscript ? 'Hide' : 'Show'} transcript
          </button>
          {showTranscript && (
            <div className={s.transcript}>{data.transcript}</div>
          )}
        </>
      )}
    </div>
  )
}
