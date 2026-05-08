import time
import requests


API_URL = "http://api-server:8000/incidents/start"

print("[alertmanager] Starting up. Will probe api-server for readiness...")

# Robust retry: poll until api-server responds, then fire the alert
max_attempts = 30
for attempt in range(1, max_attempts + 1):
    try:
        health = requests.get("http://api-server:8000/health", timeout=3)
        if health.status_code < 500:
            print(f"[alertmanager] api-server is ready (attempt {attempt}). Firing incident.")
            break
    except Exception as e:
        print(f"[alertmanager] api-server not ready (attempt {attempt}): {e}. Retrying in 5s...")
        time.sleep(5)
else:
    print("[alertmanager] api-server never became ready. Giving up.")
    raise SystemExit(1)

# Small buffer so uvicorn is fully initialized
time.sleep(2)

payload = {
    "alertId": "alert-auto-001",
    "severity": "critical",
    "service": "backend-api",
    "errorMessage": "OOMKilled pod backend-api: container exceeded memory limit",
    "runbookTags": ["OOM", "memory", "kubernetes"],
}

try:
    response = requests.post(API_URL, json=payload, timeout=10)
    print(f"[alertmanager] Response {response.status_code}: {response.text}")
except Exception as e:
    print(f"[alertmanager] Failed to fire alert: {e}")