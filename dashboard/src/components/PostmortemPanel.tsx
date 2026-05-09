import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { getPostmortem, getStatus } from '../api'

export default function PostmortemPanel({ workflowId }: { workflowId: string | null }) {
  const [content, setContent] = useState<string | null>(null)

  useEffect(() => {
    setContent(null)
    if (!workflowId) return

    let cancelled = false

    const attempt = async () => {
      try {
        const s = await getStatus(workflowId)
        if (cancelled) return
        if (s.status !== 'COMPLETED') return

        const pm = await getPostmortem(workflowId)
        if (!cancelled) setContent(pm.content)
      } catch {
        // Will retry on next tick
      }
    }

    attempt()
    const id = setInterval(attempt, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [workflowId])

  return (
    <div className="border border-gray-300 bg-white">
      <div className="p-2 border-b border-gray-300 font-bold bg-gray-100 flex justify-between">
        <span>Postmortem</span>
      </div>

      <div className="max-h-96 overflow-y-auto p-4">
        {!workflowId && <div className="text-gray-500">No incident selected</div>}
        {workflowId && !content && <div className="text-gray-500">Postmortem generated after workflow completes...</div>}
        {content && (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}
