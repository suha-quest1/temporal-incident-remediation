import { useEffect, useState } from 'react'
import { getStatus, type WorkflowResult } from '../api'

interface LogLine {
  id: number
  ts: string
  text: string
}

let _id = 0

function extractLogStrings(r: WorkflowResult, status: string): string[] {
  const lines: string[] = []
  if (r.classification) lines.push(`[classify] type=${r.classification.incident_type} severity=${r.classification.severity}`)
  if (r.runbooks) lines.push(`[runbook] fetched ${r.runbooks.length} chars of remediation guidance`)
  if (r.plan?.length) {
    lines.push(`[plan] generated ${r.plan.length} step(s):`)
    r.plan.forEach((cmd, i) => lines.push(`  ${i + 1}. ${cmd}`))
  }
  if (r.execution_results?.length) {
    lines.push(`[execute] running ${r.execution_results.length} child workflow(s)...`)
    r.execution_results.forEach((ex, i) => {
      lines.push(`  step-${i + 1} [${ex.status}] $ ${ex.command}`)
      if (ex.output) lines.push(`           -> ${ex.output.substring(0, 80)}`)
    })
  }
  if (r.rollback_result) {
    lines.push('[rollback] executing rollback sequence:')
    r.rollback_result.forEach(rb => lines.push(`  ${rb}`))
  }
  if (r.verification) {
    const ok = r.verification.healthy
    lines.push(`[verify] ${r.verification.service} -> ${ok ? 'HEALTHY' : 'UNHEALTHY'}`)
  }
  if (r.override_action) {
    lines.push(`[signal] human override received: action=${r.override_action}`)
  }
  if (r.postmortem_path) lines.push(`[postmortem] written -> ${r.postmortem_path}`)
  if (status === 'COMPLETED') lines.push('[workflow] COMPLETED')
  return lines
}

export default function LogsPanel({ workflowId }: { workflowId: string | null }) {
  const [lines, setLines] = useState<LogLine[]>([])
  const [running, setRunning] = useState(false)

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
          const newStrings = extractLogStrings(s.result, s.status)
          setLines(prev => {
            const currentStrings = prev.map(l => l.text)
            const addedStrings = newStrings.filter(ns => !currentStrings.includes(ns))
            if (addedStrings.length === 0) return prev
            const newLogLines = addedStrings.map(text => ({
              id: ++_id,
              ts: new Date().toLocaleTimeString(),
              text
            }))
            return [...prev, ...newLogLines]
          })
        }
      } catch { /* silent */ }
    }

    poll()
    const id = setInterval(poll, 3500)
    return () => { cancelled = true; clearInterval(id) }
  }, [workflowId])


  return (
    <div className="border border-gray-300 bg-white">
      <div className="p-2 border-b border-gray-300 font-bold bg-gray-100 flex justify-between">
        <span>Execution Log</span>
        {running && <span className="text-sm font-normal">Running...</span>}
      </div>
      <div className="h-48 overflow-y-auto p-2 font-mono text-sm">
        {!workflowId && <div className="text-gray-500">Waiting for incident...</div>}
        {workflowId && lines.length === 0 && <div className="text-gray-500">No logs yet.</div>}
        {lines.map(l => (
          <div key={l.id} className="mb-1">
            <span className="mr-4 text-gray-500">{l.ts}</span>
            <span>{l.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
