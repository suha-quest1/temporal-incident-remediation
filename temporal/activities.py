from temporalio import activity
import json
import re
from pathlib import Path

import httpx

from temporal.logger import logger
from temporal.llm_client import get_groq_client

# ── Paths anchored to this file, not the CWD ────────────────────────────────
_HERE = Path(__file__).parent.parent          # /app  (one level above temporal/)
_RUNBOOK_PATH = _HERE / "runbooks" / "error_handling.json"
_OUTPUT_DIR   = _HERE / "output"

MODEL = "llama-3.1-8b-instant"


def _extract_json(text: str) -> str:
    """
    Strip markdown code fences and extract the first valid JSON block.
    Handles ```json, ```, ''' wrappers and leading/trailing prose.
    """
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.strip()

    # If there's still non-JSON prose before the first [ or {, trim it
    for start_char in ("{", "["):
        idx = text.find(start_char)
        if idx != -1:
            # find matching close bracket from the right
            close_char = "}" if start_char == "{" else "]"
            end_idx = text.rfind(close_char)
            if end_idx != -1 and end_idx > idx:
                return text[idx : end_idx + 1]

    return text  # return as-is and let json.loads surface the error


# ── Activities ───────────────────────────────────────────────────────────────

@activity.defn
async def classifyIncident(err_msg: str) -> dict:
    logger.info("[classifyIncident] Classifying: %s", err_msg)

    prompt = (
        "You are a DevOps incident classifier.\n"
        "Return ONLY a JSON object with exactly two keys: incident_type and severity.\n"
        'incident_type must be one of: "OOM", "networking", "database", "disk"\n'
        'severity must be one of: "P1", "P2", "P3"\n'
        'Example: {"incident_type": "OOM", "severity": "P1"}\n\n'
        f"Incident message: {err_msg[:300]}"  # cap at 300 chars
    )

    logger.info("[Groq] classifyIncident: sending request")
    try:
        groq = get_groq_client()
        response = groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=60,
        )
        raw = response.choices[0].message.content
        logger.info("[Groq] classifyIncident raw: %s", raw)
        result = json.loads(_extract_json(raw))
        # Validate required keys
        if "incident_type" not in result or "severity" not in result:
            raise ValueError(f"Missing keys in: {result}")
        return result
    except Exception as e:
        logger.error("[Groq] classifyIncident failed: %s", e)
        return {"incident_type": "OOM", "severity": "P2"}


@activity.defn
async def fetchRunbook(runbook_tags: list[str]) -> str:
    logger.info("[fetchRunbook] Tags: %s", runbook_tags)

    try:
        with open(_RUNBOOK_PATH, "r") as f:
            runbook = json.load(f)
    except Exception as e:
        logger.error("[fetchRunbook] Failed to load runbook: %s", e)
        return ""

    matched_steps: list[str] = []

    for incident_type, data in runbook.items():
        # Match by incident_type key directly (from classifyIncident result)
        # or by any tag overlap with runbook_tags
        tags = [t.lower() for t in data.get("tags", [])]
        hits = [t for t in runbook_tags if t.lower() in tags or t.lower() == incident_type.lower()]
        if hits:
            matched_steps.extend(data.get("solution", []))

    result = "; ".join(matched_steps[:6])  # cap at 6 steps to keep prompt small
    logger.info("[fetchRunbook] Matched %d steps", len(matched_steps))
    return result


@activity.defn
async def generate_plan(incident_type: str, runbook: str, severity: str) -> list[str]:
    logger.info("[generate_plan] type=%s sev=%s", incident_type, severity)

    runbook_snippet = runbook[:400] if runbook else "No runbook available"

    prompt = (
        "You are a Kubernetes SRE. Return ONLY a JSON array of 3-5 kubectl/shell commands.\n"
        "No explanations. No markdown. Just a JSON array.\n"
        'Example: ["kubectl get pods", "kubectl describe pod api"]\n\n'
        f"Incident type: {incident_type}\n"
        f"Severity: {severity}\n"
        f"Runbook guidance: {runbook_snippet}"
    )

    logger.info("[Groq] generate_plan: sending request")
    try:
        groq = get_groq_client()
        response = groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content
        logger.info("[Groq] generate_plan raw: %s", raw)
        parsed = json.loads(_extract_json(raw))
        if not isinstance(parsed, list):
            raise ValueError(f"Expected list, got {type(parsed)}")
        # Ensure all items are strings and cap at 5
        return [str(cmd) for cmd in parsed[:5]]
    except Exception as e:
        logger.error("[Groq] generate_plan failed: %s", e)
        return [
            "kubectl get pods -n default",
            f"kubectl describe pod -l app=backend-api",
            "kubectl rollout restart deployment/backend-api",
        ]


@activity.defn
async def execute_step(command: str) -> dict:
    logger.info("[execute_step] Running: %s", command)
    url = "http://mock-k8s:8090/execute"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.post(url, json={"command": command})
            response.raise_for_status()
            result = response.json()
    except Exception as e:
        logger.error("[execute_step] HTTP call failed: %s", e)
        raise  # Re-raise so Temporal can retry/fail the activity

    if result.get("status") == "failed":
        raise Exception(f"mock-k8s rejected command '{command}': {result.get('output')}")

    return {
        "command": command,
        "status": result["status"],
        "output": result["output"],
    }


@activity.defn
async def rollback_changes(commands: list[str]) -> list[str]:
    logger.info("[rollback_changes] Reversing %d commands", len(commands))
    rollback_log = []
    for cmd in reversed(commands):
        entry = f"rollback: {cmd}"
        logger.info(entry)
        rollback_log.append(entry)
    return rollback_log


@activity.defn
async def verify_resolution(service: str) -> dict:
    logger.info("[verify_resolution] Probing health for: %s", service)
    url = "http://mock-service:8080/health"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error("[verify_resolution] Health probe failed: %s", e)
        return {"service": service, "healthy": False, "error": str(e)}

    return {
        "service": service,
        "healthy": data.get("status") == "healthy",
        "response": data,
    }


@activity.defn
async def generate_postmortem(
    incident_id: str,
    classification: dict,
    plan: list[str],
    execution_results: list[dict],
    verification: dict,
    override_action: str | None,
) -> str:
    logger.info("[generate_postmortem] Generating for incident: %s", incident_id)

    # Build a compact summary to keep the prompt small
    exec_summary = "; ".join(
        f"{r.get('command','?')}→{r.get('status','?')}" for r in execution_results[:5]
    )
    plan_summary = "; ".join(plan[:5])

    prompt = (
        "Write a short Incident Postmortem in markdown with these sections: "
        "Summary, Root Cause, Actions Taken, Verification, Lessons Learned.\n\n"
        f"Incident ID: {incident_id}\n"
        f"Type: {classification.get('incident_type')} | Severity: {classification.get('severity')}\n"
        f"Plan: {plan_summary}\n"
        f"Execution: {exec_summary}\n"
        f"Healthy after fix: {verification.get('healthy')}\n"
        f"Override: {override_action or 'none'}"
    )

    logger.info("[Groq] generate_postmortem: sending request")
    try:
        groq = get_groq_client()
        response = groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        report = response.choices[0].message.content
        logger.info("[Groq] generate_postmortem: received %d chars", len(report))
    except Exception as e:
        logger.error("[Groq] generate_postmortem failed: %s", e)
        report = (
            f"# Incident Postmortem\n\n"
            f"**Incident ID:** {incident_id}\n"
            f"**Classification:** {classification}\n"
            f"**Plan:** {plan_summary}\n"
            f"**Verification:** {verification}\n\n"
            f"_Postmortem LLM generation failed: {e}_"
        )

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = _OUTPUT_DIR / f"postmortem-{incident_id}.md"
    filepath.write_text(report, encoding="utf-8")
    logger.info("[generate_postmortem] Written to %s", filepath)
    return str(filepath)