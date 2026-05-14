from temporalio import activity
import json
from pathlib import Path

import httpx

from temporal.logger import logger
from temporal.llm_client import get_groq_client

from datetime import datetime, timezone

_HERE = Path(__file__).parent.parent
_RUNBOOK_PATH = _HERE / "runbooks" / "error_handling.json"
_OUTPUT_DIR = _HERE / "output"

#MODEL = "llama-3.1-8b-instant" 
MODEL= "openai/gpt-oss-20b"

@activity.defn(name="ClassifyIncident")
async def ClassifyIncident(err_msg: str) -> dict:
    logger.info("[ClassifyIncident] raw input: %s", err_msg)

    prompt = (
        "You are a DevOps incident classifier. Classify the incident message below.\n\n"
        "Return ONLY a valid JSON object with exactly two keys: incident_type and severity.\n\n"
        "incident_type rules:\n"
        '  - "OOM"        → keywords: OOMKilled, memory limit, out of memory, heap, container killed\n'
        '  - "database"   → keywords: postgres, mysql, connection timeout, max_connections, deadlock, db\n'
        '  - "networking" → keywords: connection refused, upstream, ingress, DNS, network, unreachable, timeout\n'
        '  - "disk"       → keywords: disk pressure, no space left, PVC, volume, storage, 9x% used\n'
        "  Use the type whose keywords best match. If none match, still pick the closest one.\n\n"
        "severity rules:\n"
        '  - "P1" → service is completely down, data loss risk, or customer-facing outage\n'
        '  - "P2" → service degraded, high error rate, approaching limits\n'
        '  - "P3" → warning-level, non-urgent, informational\n\n'
        'Example output: {"incident_type": "OOM", "severity": "P1"}\n\n'
        f"Incident message: {err_msg[:400]}"
    )

    logger.info("[Groq] ClassifyIncident: sending request")
    try:
        groq = get_groq_client()
        response = await groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=60,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        logger.info("[Groq] ClassifyIncident raw response: %s", raw)
        result = json.loads(raw)

        incident_type = result.get("incident_type")
        severity = result.get("severity")

        valid_types = {"OOM", "networking", "database", "disk"}
        valid_severities = {"P1", "P2", "P3"}

        if incident_type not in valid_types or severity not in valid_severities:
            logger.warning(
                "[ClassifyIncident] invalid response (will retry): incident_type=%r severity=%r — raw: %s",
                incident_type, severity, raw,
            )
            raise ValueError(
                f"LLM returned out-of-vocab classification: incident_type={incident_type!r} severity={severity!r}"
            )

        logger.info("[ClassifyIncident] result: incident_type=%s severity=%s", incident_type, severity)
        return result
    except Exception as e:
        logger.error("[ClassifyIncident] FAILED — no fallback, re-raising. error=%s", e)
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

    prompt = f"""\
You are a Kubernetes SRE generating a remediation plan.

Return a JSON object with a single key "commands" containing an array of 3 to 5 kubectl/shell remediation commands.

STRICT RULES:
- Output MUST be a JSON object: {{"commands": ["...", ...]}}
- Each command MUST be a plain shell string.
- Return between 3 and 5 commands.
- Prefer kubectl commands.
- No markdown, no explanations, no extra keys.

EXAMPLE OUTPUT:
{{"commands": ["kubectl get pods -A", "kubectl describe pod backend-api", "kubectl rollout restart deployment/backend-api"]}}

INCIDENT TYPE: {incident_type}
SEVERITY: {severity}
RUNBOOK: {runbook_snippet}
"""

    _PLAN_SCHEMA = {
        "type": "json_schema",
        "json_schema": {
            "name": "remediation_plan",
            "schema": {
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 5,
                    }
                },
                "required": ["commands"],
            },
        },
    }

    _FALLBACK_COMMANDS = [
        "kubectl get pods -A",
        "kubectl describe pod -l app=backend-api",
        "kubectl rollout restart deployment/backend-api",
    ]

    logger.info("[Groq] GeneratePlan: sending request")
    try:
        groq = get_groq_client()
        response = await groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
            response_format=_PLAN_SCHEMA,
        )
        raw = response.choices[0].message.content
        logger.info("[Groq] GeneratePlan raw: %s", raw)
        parsed = json.loads(raw)
        commands = parsed.get("commands")
        if not isinstance(commands, list) or not all(
            isinstance(c, str) for c in commands
        ):
            raise ValueError(f"Invalid 'commands' field in response: {parsed}")
        return commands[:5]
    except Exception as e:
        logger.error("[Groq] GeneratePlan failed (%s) — using fallback commands", e)
        return _FALLBACK_COMMANDS


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

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

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
