import s from './UploadProgressBar.module.css'

const STEPS = ['uploading', 'processing', 'ready']
const LABELS = { uploading: '⬆️ Uploading', processing: '⚙️ Processing', ready: '✅ Ready', failed: '❌ Failed' }

export default function UploadProgressBar({ status }) {
  const idx   = STEPS.indexOf(status)
  const pct   = status === 'ready' ? 100 : status === 'uploading' ? 33 : status === 'processing' ? 66 : 0
  const isFail = status === 'failed'

  return (
    <div className={s.bar}>
      <div className={s.label}>
        <span className={s.status}>
          {!isFail && status !== 'ready' && <span className="spinner" style={{ width: 14, height: 14 }} />}
          {LABELS[status] || status}
        </span>
        <span>{isFail ? '' : `${pct}%`}</span>
      </div>
      <div className={s.track}>
        <div
          className={`${s.fill} ${isFail ? s.fillFailed : status === 'ready' ? s.fillReady : status === 'processing' ? s.fillProcessing : ''}`}
          style={{ width: `${isFail ? 100 : pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Upload status: ${status}`}
        />
      </div>
    </div>
  )
}
