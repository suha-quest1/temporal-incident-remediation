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
    <div className="relative min-h-screen">
      {/* Ambient glow blobs */}
      <div className="fixed top-0 left-1/4 w-96 h-96 bg-blue-900/10 rounded-full blur-3xl pointer-events-none" />
      <div className="fixed bottom-1/4 right-1/4 w-64 h-64 bg-purple-900/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <header className="relative z-20 border-b border-slate-800/60 bg-[#080b12]/95 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Logo mark */}
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-cyan-500
                            flex items-center justify-center shadow-[0_0_12px_rgba(59,130,246,0.4)]">
              <span className="text-sm font-bold text-white">T</span>
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-100 leading-tight tracking-wide">
                Incident Remediation Orchestrator
              </h1>
              <p className="text-xs text-slate-600">Temporal · Groq · Kubernetes</p>
            </div>
          </div>

          <nav className="flex items-center gap-4 text-xs">
            {activeId && (
              <span className="font-mono text-slate-600 hidden lg:block truncate max-w-xs">
                {activeId}
              </span>
            )}
            <a href="http://localhost:8081" target="_blank" rel="noreferrer"
               className="px-3 py-1.5 rounded-md border border-slate-800 text-slate-500
                          hover:border-blue-800 hover:text-blue-400 transition-colors">
              Temporal UI ↗
            </a>
            <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer"
               className="px-3 py-1.5 rounded-md border border-slate-800 text-slate-500
                          hover:border-emerald-800 hover:text-emerald-400 transition-colors">
              API Docs ↗
            </a>
          </nav>
        </div>
      </header>

      {/* Alert action bar */}
      <AlertBar onStarted={handleStarted} />

      {/* Last fired alert context banner */}
      {lastScenario && activeId && (
        <div className="relative z-10 bg-slate-900/40 border-b border-slate-800/40">
          <div className="max-w-7xl mx-auto px-6 py-2 flex items-center gap-3 text-xs text-slate-500">
            <span>{lastScenario.icon}</span>
            <span className={lastScenario.color}>{lastScenario.label}</span>
            <span className="text-slate-700">→</span>
            <span>{lastScenario.payload.service}</span>
            <span className="text-slate-700">·</span>
            <span className="text-slate-600">{lastScenario.payload.errorMessage.substring(0, 70)}…</span>
          </div>
        </div>
      )}

      {/* Main grid */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-6 grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Left column: incident list */}
        <div className="lg:col-span-1">
          <IncidentList activeId={activeId} onSelect={setActiveId} />
        </div>

        {/* Right columns: panels */}
        <div className="lg:col-span-2 flex flex-col gap-5">
          <StatusPanel workflowId={activeId} />
          <LogsPanel workflowId={activeId} />
          <PostmortemPanel workflowId={activeId} />
        </div>
      </main>
    </div>
  )
}
