import { useEffect, useState } from 'react'
import { listIncidents, type WorkflowSummary } from '../api'

const STATUS_DOT: Record<string, string> = {
  RUNNING:   'bg-yellow-400 glow-running',
  COMPLETED: 'bg-emerald-500',
  FAILED:    'bg-red-500',
  TIMED_OUT: 'bg-orange-400',
  UNKNOWN:   'bg-slate-600 animate-pulse',
}

const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-blue-400',
}

interface Props { activeId: string | null; onSelect: (id: string) => void }

export default function IncidentList({ activeId, onSelect }: Props) {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])

  useEffect(() => {
    const refresh = async () => {
      try {
        const res = await listIncidents()
        setWorkflows(res.workflows)
      } catch { /* silent */ }
    }
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="rounded-xl border border-slate-800 bg-[#0e131f] overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <span className="text-cyan-400">≡</span> Incidents
        </span>
        <span className="text-xs text-slate-600">{workflows.length} total</span>
      </div>

      {workflows.length === 0 ? (
        <div className="p-6 text-center text-xs text-slate-700">No incidents yet</div>
      ) : (
        <ul className="divide-y divide-slate-800/60 max-h-80 overflow-y-auto">
          {workflows.map(wf => {
            const isActive = wf.workflow_id === activeId
            const dotClass = STATUS_DOT[wf.status] ?? 'bg-slate-600'
            const sevClass = SEV_COLOR[(wf as any).severity ?? ''] ?? 'text-slate-500'
            const short = wf.workflow_id.split('-').slice(-1)[0] // last hex segment
            return (
              <li
                key={wf.workflow_id}
                onClick={() => onSelect(wf.workflow_id)}
                className={`flex items-center gap-3 px-5 py-3 cursor-pointer transition-colors
                  ${isActive ? 'bg-slate-800/70' : 'hover:bg-slate-900/60'}`}
              >
                <span className={`w-2 h-2 rounded-full shrink-0 ${dotClass}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono text-slate-300 flex items-center gap-2">
                    <span className={(wf as any).service ? 'text-slate-200' : ''}>{(wf as any).service ?? wf.workflow_id}</span>
                    <span className="text-slate-700 font-sans">#{short}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-xs ${sevClass}`}>{(wf as any).severity ?? ''}</span>
                    {wf.start_time && (
                      <span className="text-xs text-slate-700">
                        {new Date(wf.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                </div>
                <span className={`text-xs shrink-0 ${
                  wf.status === 'COMPLETED' ? 'text-emerald-600' :
                  wf.status === 'RUNNING' ? 'text-yellow-600' :
                  wf.status === 'FAILED' ? 'text-red-600' : 'text-slate-600'
                }`}>{wf.status}</span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
