import { useState } from 'react'
import './index.css'
import AlertBar from './components/AlertBar'
import StatusPanel from './components/StatusPanel'
import LogsPanel from './components/LogsPanel'
import PostmortemPanel from './components/PostmortemPanel'
import IncidentList from './components/IncidentList'
import type { AlertScenario } from './api'

export default function App() {
  const [activeId, setActiveId] = useState<string | null>(null)
  const [lastScenario, setLastScenario] = useState<AlertScenario | null>(null)

  const handleStarted = (id: string, scenario: AlertScenario) => {
    setActiveId(id)
    setLastScenario(scenario)
  }

  return (
    <div className="min-h-screen bg-white text-black p-4">
      <header className="border-b border-gray-300 pb-4 mb-4 flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold">Incident Remediation Orchestrator</h1>
          <p className="text-sm text-gray-600">Temporal · Groq · Kubernetes</p>
        </div>
        <nav className="space-x-4 text-sm">
          <a href="http://localhost:8081" target="_blank" rel="noreferrer" className="text-blue-600 underline">Temporal UI</a>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="text-blue-600 underline">API Docs</a>
        </nav>
      </header>

      <AlertBar onStarted={handleStarted} />

      {lastScenario && activeId && (
        <div className="bg-gray-100 p-2 my-4 border border-gray-300 text-sm">
          <strong>Latest Alert:</strong> {lastScenario.label} ({lastScenario.payload.service}) - {lastScenario.payload.errorMessage}
        </div>
      )}

      <main className="grid grid-cols-1 lg:grid-cols-4 gap-4 mt-4">
        <div className="lg:col-span-1 border border-gray-300 p-4">
          <IncidentList activeId={activeId} onSelect={setActiveId} />
        </div>
        <div className="lg:col-span-3 space-y-4">
          <StatusPanel workflowId={activeId} />
          <LogsPanel workflowId={activeId} />
          <PostmortemPanel workflowId={activeId} />
        </div>
      </main>
    </div>
  )
}
