import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadVideo } from '@/api/videos'
import useVideoStatus from '@/hooks/useVideoStatus'
import UploadProgressBar from '@/components/UploadProgressBar'
import s from './UploadPage.module.css'

const ACCEPTED = ['video/mp4', 'video/webm', 'video/ogg', 'video/quicktime', 'video/x-matroska']

function StatusTracker({ videoId, initialStatus }) {
  const { status } = useVideoStatus(videoId, initialStatus)
  const navigate   = useNavigate()

  if (status === 'ready') {
    setTimeout(() => navigate(`/videos/${videoId}`, { replace: true }), 1200)
  }

  return (
    <div className={s.progressSection}>
      <UploadProgressBar status={status} />
      {status === 'ready' && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-success)', marginTop: 'var(--space-3)' }}>Redirecting to player…</p>}
      {status === 'failed' && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-error)', marginTop: 'var(--space-3)' }}>Processing failed. Please try again.</p>}
    </div>
  )
}

export default function UploadPage() {
  const [file,     setFile]     = useState(null)
  const [drag,     setDrag]     = useState(false)
  const [form,     setForm]     = useState({ title: '', description: '', tags: '' })
  const [errors,   setErrors]   = useState({})
  const [apiErr,   setApiErr]   = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploaded,  setUploaded]  = useState(null)  // { id, status }
  const inputRef = useRef(null)

  const setFileChecked = (f) => {
    if (!f) return
    if (!ACCEPTED.includes(f.type)) {
      setErrors((e) => ({ ...e, file: 'Only video files are accepted (mp4, webm, mov, mkv)' }))
      return
    }
    setFile(f)
    setErrors((e) => { const n = { ...e }; delete n.file; return n })
    if (!form.title) setForm((x) => ({ ...x, title: f.name.replace(/\.[^.]+$/, '') }))
  }

  const onDrop = (e) => {
    e.preventDefault(); setDrag(false)
    setFileChecked(e.dataTransfer.files[0])
  }

  const validate = () => {
    const e = {}
    if (!file)           e.file  = 'Please select a video file'
    if (!form.title.trim()) e.title = 'Title is required'
    return e
  }

  const handleSubmit = async (ev) => {
    ev.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    setUploading(true)
    setApiErr('')
    const fd = new FormData()
    fd.append('file',        file)
    fd.append('title',       form.title)
    fd.append('description', form.description)
    if (form.tags.trim()) fd.append('tags', form.tags.trim())
    try {
      const res = await uploadVideo(fd)
      setUploaded({ id: res.id ?? res.video_id, status: res.status ?? 'uploading' })
    } catch (err) {
      setApiErr(err.message)
    } finally {
      setUploading(false)
    }
  }

  if (uploaded) {
    return (
      <div className={s.page}>
        <div className="container">
          <div className={s.layout}>
            <h1 className={s.title}>Upload in progress</h1>
            <StatusTracker videoId={uploaded.id} initialStatus={uploaded.status} />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={s.page}>
      <div className="container">
        <div className={s.layout}>
          <h1 className={s.title}>Upload a video</h1>

          {/* Drop zone */}
          <div
            className={`${s.dropZone} ${drag ? s.dropZoneActive : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Click or drop a video file here"
            onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          >
            <div className={s.dropIcon} aria-hidden>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </div>
            <div className={s.dropTitle}>
              {file ? 'Video selected' : 'Drop your video here'}
            </div>
            <div className={s.dropSub}>or click to browse · mp4, webm, mov, mkv</div>
            {file && <div className={s.dropFile}>{file.name}</div>}
            <input
              ref={inputRef}
              type="file"
              className={s.hiddenInput}
              accept="video/*"
              onChange={(e) => setFileChecked(e.target.files[0])}
              aria-label="Video file input"
            />
          </div>
          {errors.file && <span className={s.fieldError}>{errors.file}</span>}

          {apiErr && <div className="alert alert-error" style={{ marginTop: 'var(--space-4)' }}>{apiErr}</div>}

          <form className={s.form} onSubmit={handleSubmit} noValidate>
            <div className={s.field}>
              <label className={s.label} htmlFor="vid-title">Title</label>
              <input
                id="vid-title"
                type="text"
                className={s.input}
                placeholder="Give your video a title"
                value={form.title}
                onChange={(e) => setForm((x) => ({ ...x, title: e.target.value }))}
              />
              {errors.title && <span className={s.fieldError}>{errors.title}</span>}
            </div>

            <div className={s.field}>
              <label className={s.label} htmlFor="vid-desc">Description <span style={{ color: 'var(--color-text-muted)' }}>(optional)</span></label>
              <textarea
                id="vid-desc"
                className={s.textarea}
                placeholder="What is this video about?"
                value={form.description}
                onChange={(e) => setForm((x) => ({ ...x, description: e.target.value }))}
              />
            </div>

            <div className={s.field}>
              <label className={s.label} htmlFor="vid-tags">Tags <span style={{ color: 'var(--color-text-muted)' }}>(optional · comma-separated)</span></label>
              <input
                id="vid-tags"
                type="text"
                className={s.input}
                placeholder="e.g. tech, tutorial, coding"
                value={form.tags}
                onChange={(e) => setForm((x) => ({ ...x, tags: e.target.value }))}
              />
            </div>

            <button type="submit" className={s.btn} disabled={uploading}>
              {uploading && <span className="spinner" style={{ width: 16, height: 16 }} />}
              {uploading ? 'Uploading…' : 'Upload video'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
