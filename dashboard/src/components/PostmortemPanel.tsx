import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { getPostmortem, getStatus } from '../api'

export default function PostmortemPanel({ workflowId }: { workflowId: string | null }) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [note, setNote] = useState('')

  useEffect(() => {
    setContent(null)
    setNote('')
    if (!workflowId) return

    let cancelled = false

    const attempt = async () => {
      try {
        const s = await getStatus(workflowId)
        if (cancelled) return
        if (s.status !== 'COMPLETED') return   // not ready yet

        setLoading(true)
        const pm = await getPostmortem(workflowId)
        if (!cancelled) {
          setContent(pm.content)
          setNote((pm as any).note ?? '')
        }
      } catch {
        // postmortem may not exist yet — retry on next tick
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    attempt()
    const id = setInterval(attempt, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [workflowId])

  return (
    <div className="rounded-xl border border-slate-800 bg-[#0e131f] overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/40">
        <span className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <span className="text-amber-400">◈</span> Postmortem
        </span>
        {note && <span className="text-xs text-slate-600">{note}</span>}
      </div>

      <div className="max-h-96 overflow-y-auto">
        {!workflowId && (
          <Empty text="No incident selected" />
        )}
        {workflowId && !content && !loading && (
          <Empty text="Postmortem generated after workflow completes" />
        )}
        {loading && !content && (
          <Empty text="Generating postmortem…" pulse />
        )}
        {content && (
          <div className="prose prose-invert prose-sm max-w-none p-5
                          prose-headings:text-slate-200 prose-headings:font-semibold
                          prose-p:text-slate-400 prose-li:text-slate-400
                          prose-code:text-emerald-300 prose-code:bg-slate-900
                          prose-strong:text-slate-200">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

function Empty({ text, pulse }: { text: string; pulse?: boolean }) {
  return (
    <div className={`p-8 text-center text-sm text-slate-700 ${pulse ? 'animate-pulse' : ''}`}>
      {text}
    </div>
  )
}
