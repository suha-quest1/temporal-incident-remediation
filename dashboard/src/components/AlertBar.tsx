import { useState } from 'react'
import { ALERT_SCENARIOS, fireAlert, type AlertScenario } from '../api'

interface Props {
  onStarted: (workflowId: string, scenario: AlertScenario) => void
}

export default function AlertBar({ onStarted }: Props) {
  const [selected, setSelected] = useState<string>('oom')
  const [loading, setLoading] = useState(false)
  const [flashMsg, setFlashMsg] = useState<string | null>(null)

  const scenario = ALERT_SCENARIOS.find(s => s.id === selected) ?? ALERT_SCENARIOS[0]

  const fire = async () => {
    setLoading(true)
    setFlashMsg(null)
    try {
      const res = await fireAlert(scenario.payload)
      setFlashMsg(`Alert fired → ${res.workflow_id}`)
      onStarted(res.workflow_id, scenario)
    } catch (e) {
      setFlashMsg(String(e))
    } finally {
      setLoading(false)
      setTimeout(() => setFlashMsg(null), 4000)
    }
  }

  return (
    <div className="border border-gray-300 p-4 mb-4 bg-gray-50 flex items-center gap-4">
      <div>
        <label className="text-sm font-bold mr-2">Trigger Alert:</label>
        <select
          value={selected}
          onChange={e => setSelected(e.target.value)}
          className="border border-gray-400 p-1 bg-white"
        >
          {ALERT_SCENARIOS.map(s => (
            <option key={s.id} value={s.id}>
              {s.label} ({s.payload.service})
            </option>
          ))}
        </select>
      </div>

      <button
        onClick={fire}
        disabled={loading}
        className="px-4 py-1 bg-blue-600 text-white font-bold disabled:opacity-50"
      >
        {loading ? 'Firing...' : 'Send Alert'}
      </button>

      {flashMsg && <span className="text-sm text-green-700 font-bold">{flashMsg}</span>}
    </div>
  )
}
