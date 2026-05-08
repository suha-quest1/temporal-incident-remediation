import { useState } from 'react'
import { ALERT_SCENARIOS, fireAlert, type AlertScenario } from '../api'

interface Props {
  onStarted: (workflowId: string, scenario: AlertScenario) => void
}

const SEVERITY_BADGE: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-300 border-red-600/40',
  high:     'bg-orange-500/20 text-orange-300 border-orange-600/40',
  medium:   'bg-yellow-500/20 text-yellow-300 border-yellow-600/40',
  low:      'bg-blue-500/20 text-blue-300 border-blue-600/40',
}

export default function AlertBar({ onStarted }: Props) {
  const [selected, setSelected] = useState<string>('oom')
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState<'success' | 'error' | null>(null)
  const [flashMsg, setFlashMsg] = useState('')

  const scenario = ALERT_SCENARIOS.find(s => s.id === selected) ?? ALERT_SCENARIOS[0]

  const fire = async () => {
    setLoading(true)
    setFlash(null)
    try {
      const res = await fireAlert(scenario.payload)
      setFlash('success')
      setFlashMsg(`Alert fired → ${res.workflow_id}`)
      onStarted(res.workflow_id, scenario)
    } catch (e) {
      setFlash('error')
      setFlashMsg(String(e))
    } finally {
      setLoading(false)
      setTimeout(() => setFlash(null), 4000)
    }
  }

  return (
    <div className="relative z-10 border-b border-slate-800 bg-[#0c1018]/90 backdrop-blur">
      <div className="max-w-7xl mx-auto px-6 py-3 flex flex-wrap items-center gap-3">
        {/* Scenario selector */}
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2">
          <span className="text-xs text-slate-500 whitespace-nowrap">Alert type</span>
          <select
            value={selected}
            onChange={e => setSelected(e.target.value)}
            className="bg-transparent text-sm text-slate-200 outline-none cursor-pointer"
          >
            {ALERT_SCENARIOS.map(s => (
              <option key={s.id} value={s.id} className="bg-slate-900">
                {s.icon} {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Preview badge */}
        <div className="flex items-center gap-2 text-xs">
          <span className={`px-2 py-0.5 rounded border ${SEVERITY_BADGE[scenario.payload.severity] ?? SEVERITY_BADGE.low}`}>
            {scenario.payload.severity.toUpperCase()}
          </span>
          <span className="text-slate-400 hidden sm:block truncate max-w-xs">
            {scenario.payload.service} — {scenario.payload.errorMessage.substring(0, 48)}…
          </span>
        </div>

        <div className="flex-1" />

        {/* Flash message */}
        {flash && (
          <span className={`text-xs slide-in px-3 py-1 rounded-full border ${
            flash === 'success'
              ? 'bg-emerald-900/30 text-emerald-300 border-emerald-700'
              : 'bg-red-900/30 text-red-300 border-red-700'
          }`}>
            {flash === 'success' ? '✓' : '✗'} {flashMsg.substring(0, 60)}
          </span>
        )}

        {/* Fire button */}
        <button
          onClick={fire}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500
                     active:scale-95 disabled:opacity-50 transition-all text-sm font-semibold
                     shadow-[0_0_16px_rgba(239,68,68,0.35)] hover:shadow-[0_0_24px_rgba(239,68,68,0.55)]"
        >
          {loading ? (
            <>
              <Spinner /> Firing…
            </>
          ) : (
            <>
              <span>{scenario.icon}</span>
              Send Fake Alert
            </>
          )}
        </button>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}
