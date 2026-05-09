import { useEffect, useState } from 'react'
import { listIncidents, type WorkflowSummary } from '../api'

interface Props { activeId: string | null; onSelect: (id: string) => void }

export default function IncidentList({ activeId, onSelect }: Props) {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])

  useEffect(() => {
    const refresh = async () => {
      try {
        const res = await listIncidents()
        setWorkflows(prev => {
          if (JSON.stringify(prev) === JSON.stringify(res.workflows)) {
            return prev;
          }
          return res.workflows;
        })
      } catch { /* silent */ }
    }
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="border border-gray-300 bg-white">
      <div className="p-2 border-b border-gray-300 font-bold bg-gray-100 flex justify-between">
        <span>Incidents</span>
        <span className="font-normal text-sm">{workflows.length} total</span>
      </div>

      {workflows.length === 0 ? (
        <div className="p-4 text-center text-gray-500 text-sm">No incidents yet</div>
      ) : (
        <ul className="max-h-80 overflow-y-auto m-0 p-0 list-none">
          {workflows.map(wf => {
            const isActive = wf.workflow_id === activeId
            const service = (wf as any).service || 'Unknown Service'
            const severity = (wf as any).severity || ''
            
            return (
              <li
                key={wf.workflow_id}
                onClick={() => onSelect(wf.workflow_id)}
                className={`p-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 text-sm ${isActive ? 'bg-blue-50 font-bold' : ''}`}
              >
                <div className="flex justify-between items-center mb-1">
                  <span>{service}</span>
                  <span className="text-gray-500 text-xs">{wf.status}</span>
                </div>
                <div className="text-gray-600 text-xs">
                  {severity && <span className="mr-2 uppercase">{severity}</span>}
                  <span className="truncate" title={wf.workflow_id}>{wf.workflow_id.substring(0, 18)}...</span>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
