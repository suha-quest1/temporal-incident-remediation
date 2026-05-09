ERROR_MAP = {
    "oomkilled": {"incident_type": "OOM", "severity": "P1"},
    "out of memory": {"incident_type": "OOM", "severity": "P1"},
    "connection refused": {"incident_type": "networking", "severity": "P2"},
    "timed out": {"incident_type": "networking", "severity": "P2"},
    "disk full": {"incident_type": "disk", "severity": "P1"},
    "no space left": {"incident_type": "disk", "severity": "P1"},
    "deadlock detected": {"incident_type": "database", "severity": "P2"},
    "too many connections": {"incident_type": "database", "severity": "P1"},
}
