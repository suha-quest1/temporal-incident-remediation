const BASE = '/api'

// ── Alert scenarios ────────────────────────────────────────────────────────
export interface AlertScenario {
  id: string
  label: string
  icon: string
  color: string
  payload: StartIncidentPayload
}

export const ALERT_SCENARIOS: AlertScenario[] = [
  {
    id: 'oom',
    label: 'OOM Crash',
    icon: '💥',
    color: 'text-red-400',
    payload: {
      alertId: `alert-oom-${Date.now()}`,
      severity: 'critical',
      service: 'backend-api',
      errorMessage: 'OOMKilled pod backend-api: container exceeded memory limit 512Mi',
      runbookTags: ['OOM', 'memory', 'kubernetes'],
    },
  },
  {
    id: 'db',
    label: 'Database Failure',
    icon: '🗄️',
    color: 'text-orange-400',
    payload: {
      alertId: `alert-db-${Date.now()}`,
      severity: 'high',
      service: 'postgres-db',
      errorMessage: 'Database connection timeout: max_connections exceeded',
      runbookTags: ['database', 'postgres', 'connectivity'],
    },
  },
  {
    id: 'net',
    label: 'Network Failure',
    icon: '🌐',
    color: 'text-yellow-400',
    payload: {
      alertId: `alert-net-${Date.now()}`,
      severity: 'medium',
      service: 'ingress-nginx',
      errorMessage: 'Ingress gateway unreachable: upstream connection refused',
      runbookTags: ['networking', 'ingress', 'latency'],
    },
  },
  {
    id: 'disk',
    label: 'Disk Pressure',
    icon: '💾',
    color: 'text-purple-400',
    payload: {
      alertId: `alert-disk-${Date.now()}`,
      severity: 'critical',
      service: 'worker-node',
      errorMessage: 'Disk pressure threshold exceeded: 94% used on /var/lib/kubelet',
      runbookTags: ['disk', 'storage', 'node'],
    },
  },
]

// ── Types ──────────────────────────────────────────────────────────────────
export interface StartIncidentPayload {
  alertId: string
  severity: string
  service: string
  errorMessage: string
  runbookTags: string[]
}

export interface WorkflowResult {
  classification: { incident_type: string; severity: string } | null
  runbooks: string
  plan: string[]
  execution_results: { command: string; status: string; output: string }[]
  rollback_result: string[] | null
  verification: { service: string; healthy: boolean } | null
  override_action: string | null
  postmortem_path: string | null
}

export interface WorkflowStatus {
  workflow_id: string
  status: string
  start_time: string | null
  close_time: string | null
  result: WorkflowResult | null
  meta: Record<string, string>
}

export interface WorkflowSummary {
  workflow_id: string
  status: string
  start_time: string | null
  close_time: string | null
  severity?: string
  service?: string
}

// ── API calls ──────────────────────────────────────────────────────────────
export async function fireAlert(payload: StartIncidentPayload) {
  // Generate fresh alertId each time to avoid collisions
  const freshPayload = { ...payload, alertId: `${payload.alertId.split('-').slice(0, 2).join('-')}-${Date.now()}` }
  const res = await fetch(`${BASE}/incidents/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(freshPayload),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text)
  }
  return res.json() as Promise<{ message: string; workflow_id: string }>
}

export async function sendOverride(workflowId: string, action: string, engineer = 'sre-alice') {
  const res = await fetch(`${BASE}/incidents/${encodeURIComponent(workflowId)}/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, engineer }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getStatus(workflowId: string): Promise<WorkflowStatus> {
  const res = await fetch(`${BASE}/incidents/${encodeURIComponent(workflowId)}/status`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getPostmortem(workflowId: string): Promise<{ content: string }> {
  const res = await fetch(`${BASE}/incidents/${encodeURIComponent(workflowId)}/postmortem`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listIncidents(): Promise<{ workflows: WorkflowSummary[] }> {
  const res = await fetch(`${BASE}/incidents`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
