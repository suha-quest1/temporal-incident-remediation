from temporalio import activity
import json
import re
from pathlib import Path

import httpx

from temporal.logger import logger
from temporal.llm_client import get_groq_client

from datetime import datetime

_HERE = Path(__file__).parent.parent
_RUNBOOK_PATH = _HERE / "runbooks" / "error_handling.json"
_OUTPUT_DIR = _HERE / "output"

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

    for start_char in ("{", "["):
        idx = text.find(start_char)
        if idx != -1:
            close_char = "}" if start_char == "{" else "]"
            end_idx = text.rfind(close_char)
            if end_idx != -1 and end_idx > idx:
                return text[idx : end_idx + 1]

    return text


@activity.defn(name="ClassifyIncident")
async def ClassifyIncident(err_msg: str) -> dict:
    logger.info("[ClassifyIncident] Classifying: %s", err_msg)

    prompt = (
        "You are a DevOps incident classifier.\n"
        "Return ONLY a JSON object with exactly two keys: incident_type and severity.\n"
        'incident_type must be one of: "OOM", "networking", "database", "disk"\n'
        'severity must be one of: "P1", "P2", "P3"\n'
        'Example: {"incident_type": "OOM", "severity": "P1"}\n\n'
        f"Incident message: {err_msg[:300]}"
    )

    logger.info("[Groq] ClassifyIncident: sending request")
    try:
        groq = get_groq_client()
        response = await groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=60,
        )
        raw = response.choices[0].message.content
        logger.info("[Groq] ClassifyIncident raw: %s", raw)
        result = json.loads(_extract_json(raw))
        if "incident_type" not in result or "severity" not in result:
            raise ValueError(f"Missing keys in: {result}")
        return result
    except Exception as e:
        logger.error("[Groq] ClassifyIncident failed: %s", e)
        raise


@activity.defn(name="FetchRunbook")
async def FetchRunbook(runbook_tags: list[str]) -> str:
    logger.info("[FetchRunbook] Tags: %s", runbook_tags)

    try:
        with open(_RUNBOOK_PATH, "r") as f:
            runbook = json.load(f)
    except Exception as e:
        logger.error("[FetchRunbook] Failed to load runbook: %s", e)
        return ""

    matched_steps: list[str] = []

    for incident_type, data in runbook.items():
        # match by incident_type key directly or by tags
        tags = [t.lower() for t in data.get("tags", [])]
        hits = [
            t
            for t in runbook_tags
            if t.lower() in tags or t.lower() == incident_type.lower()
        ]
        if hits:
            matched_steps.extend(data.get("solution", []))

    result = "; ".join(matched_steps[:6])
    logger.info("[FetchRunbook] Matched %d steps", len(matched_steps))
    return result


@activity.defn(name="GeneratePlan")
async def GeneratePlan(incident_type: str, runbook: str, severity: str) -> list[str]:
    logger.info("[GeneratePlan] type=%s sev=%s", incident_type, severity)

    runbook_snippet = runbook[:400] if runbook else "No runbook available"

    prompt = (
        "You are a Kubernetes SRE. Return ONLY a JSON array of 3-5 kubectl/shell commands.\n"
        "No explanations. No markdown. Just a JSON array.\n"
        'Example: ["kubectl get pods", "kubectl describe pod api"]\n\n'
        f"Incident type: {incident_type}\n"
        f"Severity: {severity}\n"
        f"Runbook guidance: {runbook_snippet}"
    )

    logger.info("[Groq] GeneratePlan: sending request")
    try:
        groq = get_groq_client()
        response = await groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content
        logger.info("[Groq] GeneratePlan raw: %s", raw)
        parsed = json.loads(_extract_json(raw))
        if not isinstance(parsed, list):
            raise ValueError(f"Expected list, got {type(parsed)}")
        return [str(cmd) for cmd in parsed[:5]]
    except Exception as e:
        logger.error("[Groq] GeneratePlan failed: %s", e)
        raise


@activity.defn(name="ExecuteStep")
async def ExecuteStep(command: str) -> dict:
    logger.info("[ExecuteStep] Running: %s", command)
    url = "http://mock-k8s:8090/execute"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.post(url, json={"command": command})
            response.raise_for_status()
            result = response.json()
    except Exception as e:
        logger.error("[ExecuteStep] HTTP call failed: %s", e)
        raise

    if result.get("status") == "failed":
        raise Exception(
            f"mock-k8s rejected command '{command}': {result.get('output')}"
        )

    return {
        "command": command,
        "status": result["status"],
        "output": result["output"],
    }


@activity.defn(name="RollbackChanges")
async def RollbackChanges(commands: list[str]) -> list[str]:
    logger.info("[RollbackChanges] Reversing %d commands", len(commands))
    rollback_log = []
    for cmd in reversed(commands):
        entry = f"rollback: {cmd}"
        logger.info(entry)
        rollback_log.append(entry)
    return rollback_log


@activity.defn(name="VerifyResolution")
async def VerifyResolution(service: str) -> dict:
    logger.info("[VerifyResolution] Probing health for: %s", service)
    url = "http://mock-service:8080/health"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error("[VerifyResolution] Health probe failed: %s", e)
        return {"service": service, "healthy": False, "error": str(e)}

    return {
        "service": service,
        "healthy": data.get("status") == "healthy",
        "response": data,
    }


@activity.defn(name="GeneratePostmortem")
async def GeneratePostmortem(
    incident_id: str,
    classification: dict,
    plan: list[str],
    execution_results: list[dict],
    verification: dict,
    override_action: str | None,
) -> str:

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    logger.info("[GeneratePostmortem] Generating for incident: %s", incident_id)

    exec_summary = "; ".join(
        f"{r.get('command','?')}->{r.get('status','?')}" for r in execution_results[:5]
    )
    plan_summary = "; ".join(plan[:5])

    prompt = f"""
You are generating a REAL DevOps incident report.

STRICT RULES:
- Use concise operational language
- NO fluff
- NO storytelling
- NO explanations unless directly supported by input
- NO placeholder text like [Date], [Time], or <incident_id>
- DO NOT invent causes like memory leaks unless explicitly provided
- DO NOT mention things not present in the incident data
- Keep sentences short and direct
- Output VALID markdown ONLY

OUTPUT FORMAT (follow EXACTLY):

# Incident Report — {incident_id}

Date: {timestamp}

Severity: {classification.get("severity")}
Issue Type: {classification.get("incident_type")}

## Actions
- ...
- ...

## Result
- ...

## Follow-Up
- ...
- ...

INCIDENT DATA:

Incident ID:
{incident_id}

Timestamp:
{timestamp}

Incident Type:
{classification.get("incident_type")}

Severity:
{classification.get("severity")}

Remediation Plan:
{plan_summary}

Execution Results:
{exec_summary}

Healthy After Fix:
{verification.get("healthy")}

Override Action:
{override_action or "none"}

Remember:
- concise
- operational
- factual only
- no hallucinated root causes
"""

    logger.info("[Groq] GeneratePostmortem: sending request")
    try:
        groq = get_groq_client()
        response = await groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        report = response.choices[0].message.content
        logger.info("[Groq] GeneratePostmortem: received %d chars", len(report))
    except Exception as e:
        logger.error("[Groq] GeneratePostmortem failed: %s", e)
        raise

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = _OUTPUT_DIR / f"postmortem-{incident_id}.md"
    filepath.write_text(report, encoding="utf-8")
    logger.info("[GeneratePostmortem] Written to %s", filepath)
    return str(filepath)
