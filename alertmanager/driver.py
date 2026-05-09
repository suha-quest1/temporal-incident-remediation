import time
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("alertmanager")

API_URL = "http://api-server:8000/incidents/start"

logger.info("Starting up. Will probe api-server for readiness...")

max_attempts = 30
for attempt in range(1, max_attempts + 1):
    try:
        health = requests.get("http://api-server:8000/health", timeout=3)
        if health.status_code < 500:
            logger.info("api-server is ready (attempt %d). Firing incident.", attempt)
            break
    except Exception as e:
        logger.warning("api-server not ready (attempt %d): %s. Retrying in 5s...", attempt, e)
        time.sleep(5)
else:
    logger.error("api-server never became ready. Giving up.")
    raise SystemExit(1)

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
    logger.info("Response %s: %s", response.status_code, response.text)
except Exception as e:
    logger.error("Failed to fire alert: %s", e)