import { useEffect, useRef, useState } from 'react'
import { getStatus, type WorkflowResult } from '../api'

interface LogLine {
  id: number
  ts: string
  level: 'info' | 'ok' | 'err' | 'warn' | 'dim'
  text: string
}

let _id = 0
const mkLine = (level: LogLine['level'], text: string): LogLine => ({
  id: ++_id, ts: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }), level, text,
})

function buildLines(r: WorkflowResult, status: string): LogLine[] {
  const lines: LogLine[] = []

  if (r.classification) {
    lines.push(mkLine('info', `[classify] type=${r.classification.incident_type} severity=${r.classification.severity}`))
  }
  if (r.runbooks) {
    lines.push(mkLine('dim', `[runbook] fetched ${r.runbooks.length} chars of remediation guidance`))
  }
  if (r.plan?.length) {
    lines.push(mkLine('info', `[plan] generated ${r.plan.length} step(s):`))
    r.plan.forEach((cmd, i) => lines.push(mkLine('dim', `  ${i + 1}. ${cmd}`)))
  }
  if (r.execution_results?.length) {
    lines.push(mkLine('info', `[execute] running ${r.execution_results.length} child workflow(s)…`))
    r.execution_results.forEach((ex, i) => {
      const lvl = ex.status === 'success' ? 'ok' : 'err'
      lines.push(mkLine(lvl, `  step-${i + 1} [${ex.status}] $ ${ex.command}`))
      if (ex.output) lines.push(mkLine('dim', `           → ${ex.output.substring(0, 80)}`))
    })
  }
  if (r.rollback_result) {
    lines.push(mkLine('warn', '[rollback] executing rollback sequence:'))
    r.rollback_result.forEach(rb => lines.push(mkLine('warn', `  ${rb}`)))
  }
  if (r.verification) {
    const ok = r.verification.healthy
    lines.push(mkLine(ok ? 'ok' : 'err', `[verify] ${r.verification.service} → ${ok ? 'HEALTHY ✓' : 'UNHEALTHY ✗'}`))
  }
  if (r.override_action) {
    lines.push(mkLine('warn', `[signal] human override received: action=${r.override_action}`))
  }
  if (r.postmortem_path) {
    lines.push(mkLine('ok', `[postmortem] written → ${r.postmortem_path}`))
  }
  if (status === 'COMPLETED') {
    lines.push(mkLine('ok', '[workflow] COMPLETED ✓'))
  }
  return lines
}

const LEVEL_CLASS: Record<LogLine['level'], string> = {
  info: 'text-sky-400',
  ok:   'text-emerald-400',
  err:  'text-red-400',
  warn: 'text-yellow-400',
  dim:  'text-slate-500',
}

export default function LogsPanel({ workflowId }: { workflowId: string | null }) {
  const [lines, setLines] = useState<LogLine[]>([])
  const [running, setRunning] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLines([])
    setRunning(false)
    if (!workflowId) return

    let cancelled = false
    const poll = async () => {
      try {
        const s = await getStatus(workflowId)
        if (cancelled) return
        setRunning(s.status === 'RUNNING')
        if (s.result) {
          setLines(buildLines(s.result, s.status))
        }
      } catch { /* silent */ }
    }

    poll()
    const id = setInterval(poll, 3500)
    return () => { cancelled = true; clearInterval(id) }
  }, [workflowId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  return (
    <div className="rounded-xl border border-slate-800 bg-[#0e131f] overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/40">
        <span className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <span className="text-purple-400">▶</span> Execution Log
        </span>
        {running && (
          <span className="flex items-center gap-1.5 text-xs text-yellow-500">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
            live
          </span>
        )}
      </div>

      <div className="h-52 overflow-y-auto p-4 font-mono text-xs space-y-0.5 bg-[#080b10]">
        {!workflowId && (
          <span className="text-slate-700">Waiting for incident…</span>
        )}
        {workflowId && lines.length === 0 && !running && (
          <span className="text-slate-700">No output yet.</span>
        )}
        {running && lines.length === 0 && (
          <span className="text-yellow-600 animate-pulse">orchestration in progress…</span>
        )}
        {lines.map(l => (
          <div key={l.id} className="flex gap-3 slide-in">
            <span className="text-slate-700 shrink-0 select-none">{l.ts}</span>
            <span className={LEVEL_CLASS[l.level]}>{l.text}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
