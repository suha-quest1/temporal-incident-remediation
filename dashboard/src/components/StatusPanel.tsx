import { useEffect, useRef, useState } from 'react'
import { getStatus, sendOverride, type WorkflowResult, type WorkflowStatus } from '../api'

const STATUS_CONFIG: Record<string, { label: string; dot: string; text: string; border: string }> = {
  RUNNING:    { label: 'RUNNING',    dot: 'bg-yellow-400 glow-running', text: 'text-yellow-300', border: 'border-yellow-700/50' },
  COMPLETED:  { label: 'COMPLETED',  dot: 'bg-emerald-400',             text: 'text-emerald-300', border: 'border-emerald-700/50' },
  FAILED:     { label: 'FAILED',     dot: 'bg-red-500',                 text: 'text-red-300',     border: 'border-red-700/50' },
  TIMED_OUT:  { label: 'TIMED OUT',  dot: 'bg-orange-400',              text: 'text-orange-300',  border: 'border-orange-700/50' },
  CANCELLED:  { label: 'CANCELLED',  dot: 'bg-slate-500',               text: 'text-slate-400',   border: 'border-slate-700' },
  UNKNOWN:    { label: 'UNKNOWN',    dot: 'bg-slate-600 animate-pulse', text: 'text-slate-400',   border: 'border-slate-700' },
}

const PHASES = [
  'classifyIncident',
  'fetchRunbook',
  'generatePlan',
  'executeSteps',
  'awaitOverride',
  'verifyResolution',
  'generatePostmortem',
]

function inferPhase(result: WorkflowResult | null, status: string): number {
  if (status !== 'RUNNING') return result ? PHASES.length : 0
  if (!result) return 0
  if (result.postmortem_path) return 6
  if (result.verification) return 5
  if (result.override_action !== undefined) return 4
  if (result.execution_results?.length) return 3
  if (result.plan?.length) return 2
  if (result.runbooks) return 1
  return 0
}

interface Props {
  workflowId: string | null
}

export default function StatusPanel({ workflowId }: Props) {
  const [wfStatus, setWfStatus] = useState<WorkflowStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signalMsg, setSignalMsg] = useState<string | null>(null)
  const [signalLoading, setSignalLoading] = useState(false)
  const prevId = useRef<string | null>(null)

  useEffect(() => {
    if (workflowId !== prevId.current) {
      setWfStatus(null)
      setError(null)
      setSignalMsg(null)
      prevId.current = workflowId
    }
    if (!workflowId) return

    let cancelled = false
    const poll = async () => {
      try {
        const s = await getStatus(workflowId)
        if (!cancelled) { setWfStatus(s); setError(null) }
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
    }

    poll()
    const id = setInterval(poll, 3500)
    return () => { cancelled = true; clearInterval(id) }
  }, [workflowId])

  const sendSignal = async (action: string) => {
    if (!workflowId) return
    setSignalLoading(true)
    setSignalMsg(null)
    try {
      await sendOverride(workflowId, action)
      setSignalMsg(`✓ ${action} signal sent`)
    } catch (e) {
      setSignalMsg(`✗ ${String(e)}`)
    } finally {
      setSignalLoading(false)
    }
  }

  if (!workflowId) return <EmptyState />

  const cfg = STATUS_CONFIG[wfStatus?.status ?? 'UNKNOWN'] ?? STATUS_CONFIG.UNKNOWN
  const r = wfStatus?.result ?? null
  const phaseIdx = inferPhase(r, wfStatus?.status ?? 'UNKNOWN')
  const isComplete = wfStatus?.status === 'COMPLETED'
  const isRunning = wfStatus?.status === 'RUNNING'

  return (
    <div className="rounded-xl border border-slate-800 bg-[#0e131f] overflow-hidden slide-in">
      {/* Status header */}
      <div className={`flex items-center justify-between px-5 py-3 border-b ${cfg.border} bg-slate-900/40`}>
        <div className="flex items-center gap-3">
          <span className={`w-2.5 h-2.5 rounded-full ${cfg.dot}`} />
          <span className={`text-sm font-bold tracking-wider ${cfg.text}`}>{cfg.label}</span>
          {isRunning && <span className="text-xs text-slate-500 animate-pulse">● polling…</span>}
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          {wfStatus?.start_time && <span>↑ {fmt(wfStatus.start_time)}</span>}
          {wfStatus?.close_time && <span>↓ {fmt(wfStatus.close_time)}</span>}
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* Workflow ID */}
        <div className="font-mono text-xs text-slate-600 truncate">
          <span className="text-slate-700">wf/</span>{workflowId}
        </div>

        {error && (
          <div className="text-xs bg-red-950/50 border border-red-800/50 rounded-lg px-3 py-2 text-red-400">
            {error}
          </div>
        )}

        {/* Pipeline progress */}
        <div>
          <div className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Pipeline</div>
          <div className="flex gap-0.5">
            {PHASES.map((phase, i) => (
              <div key={phase} className="flex-1 group relative">
                <div className={`h-1.5 rounded-sm transition-all duration-500 ${
                  i < phaseIdx
                    ? 'bg-emerald-500'
                    : i === phaseIdx && isRunning
                    ? 'bg-yellow-400 animate-pulse'
                    : 'bg-slate-800'
                }`} />
                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100
                               bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-xs text-slate-300
                               whitespace-nowrap pointer-events-none z-10 transition-opacity">
                  {phase}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-1 text-xs text-slate-600">
            {isRunning ? `${PHASES[phaseIdx] ?? '…'}` : isComplete ? 'Complete' : ''}
          </div>
        </div>

        {/* Classification */}
        {r?.classification && (
          <div className="grid grid-cols-2 gap-3">
            <Card label="Incident Type" value={r.classification.incident_type} accent="text-blue-300" />
            <Card label="Severity" value={r.classification.severity}
                  accent={r.classification.severity === 'P1' ? 'text-red-300' : r.classification.severity === 'P2' ? 'text-orange-300' : 'text-yellow-300'} />
          </div>
        )}

        {/* Plan */}
        {r?.plan && r.plan.length > 0 && (
          <div>
            <div className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Remediation Plan</div>
            <div className="space-y-1">
              {r.plan.map((cmd, i) => {
                const ex = r.execution_results?.[i]
                return (
                  <div key={i} className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-mono
                    ${ex?.status === 'success' ? 'bg-emerald-950/30 border border-emerald-900/50'
                      : ex?.status === 'failed' ? 'bg-red-950/30 border border-red-900/50'
                      : 'bg-slate-900/60 border border-slate-800'}`}>
                    <span className="text-slate-600 w-4 shrink-0">{i + 1}.</span>
                    <span className="text-slate-300 truncate flex-1">{cmd}</span>
                    {ex && (
                      <span className={ex.status === 'success' ? 'text-emerald-400' : 'text-red-400'}>
                        {ex.status === 'success' ? '✓' : '✗'}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Verification */}
        {r?.verification && (
          <div className={`flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm border
            ${r.verification.healthy
              ? 'bg-emerald-950/30 border-emerald-800/50 text-emerald-300'
              : 'bg-red-950/30 border-red-800/50 text-red-300'}`}>
            <span className="text-base">{r.verification.healthy ? '✓' : '✗'}</span>
            <span>
              {r.verification.service} — {r.verification.healthy ? 'Service Healthy' : 'Unhealthy'}
            </span>
          </div>
        )}

        {/* Override signals */}
        <div className="pt-2 border-t border-slate-800 flex gap-2">
          <button
            onClick={() => sendSignal('rollback')}
            disabled={signalLoading || isComplete || !isRunning}
            className="flex-1 py-2 text-xs font-semibold rounded-lg bg-red-900/40 hover:bg-red-900/70
                       border border-red-800/50 text-red-300 disabled:opacity-30 transition-all"
          >
            ↩ Rollback
          </button>
          <button
            onClick={() => sendSignal('approve')}
            disabled={signalLoading || isComplete || !isRunning}
            className="flex-1 py-2 text-xs font-semibold rounded-lg bg-emerald-900/40 hover:bg-emerald-900/70
                       border border-emerald-800/50 text-emerald-300 disabled:opacity-30 transition-all"
          >
            ✓ Approve
          </button>
        </div>
        {signalMsg && (
          <p className="text-center text-xs text-slate-400 slide-in">{signalMsg}</p>
        )}
      </div>
    </div>
  )
}

function Card({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3">
      <div className="text-xs text-slate-600 mb-1">{label}</div>
      <div className={`text-base font-bold ${accent}`}>{value}</div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#0e131f] p-8 text-center">
      <div className="text-3xl mb-3 opacity-30">📡</div>
      <div className="text-slate-600 text-sm">No active incident</div>
      <div className="text-slate-700 text-xs mt-1">Fire an alert to begin orchestration</div>
    </div>
  )
}

function fmt(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
