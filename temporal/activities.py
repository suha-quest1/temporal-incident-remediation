from temporalio import activity
import json
from temporal.logger import logger
from temporal.data.error_map import ERROR_MAP
from pathlib import Path
import httpx

#where do i put this?? oh this is where the logger message is supposed to go...smh
#logger.info(f"Classifying: {error_message}")

@activity.defn
async def classifyIncident(err_msg: str) -> dict:
    logger.info(f"Classifying incident: {err_msg}")
    
    error= err_msg.lower()
    for keyword, classification in ERROR_MAP.items():
        if keyword.lower() in error:
            return classification
        
    return { "incident_type": "Unknown", "severity": "P2"}
            
    
@activity.defn
async def fetchRunbook(runbook_tags: list[str])-> str:
    logger.info("Fetching solutions from runbook")

    solution=[]

    with open("./runbooks/error_handling.json", "r") as f:
        runbook=json.load(f)
        for item in runbook_tags:
            if item in runbook:
                solution.extend(runbook[item]["solution"])
    return " ".join(solution)


'''Produces commands (source: some fake text file), pipeline puts them into exec_commands.sh?? no, just ''' 
@activity.defn
async def generate_plan(incident_type: str, runbook: str, severity: str) -> list[str]:

    logger.info(f"Generating remediation plan for {incident_type}")

    with open("./fakes/fake_llm_commands.txt", "r") as f:
        commands = f.readlines()

    return [cmd.strip() for cmd in commands if cmd.strip()]

'''fake activity for the child workflow thing:'''
@activity.defn
async def execute_step(command: str) -> dict:

    logger.info(f"Executing command: {command}")

    if "restart" in command:
        raise Exception("Mock Kubernetes restart failure")

    return {
        "command": command,
        "status": "success",
        "output": f"would execute: {command}"
    }



'''rollback'''
@activity.defn
async def rollback_changes(commands: list[str]) -> list[str]:

    logger.info("Rolling back commands")
    reversed_cmds = list(reversed(commands))

    rollback_log = []

    for cmd in reversed_cmds:
        rollback_cmd = f"rollback: {cmd}"
        logger.info(rollback_cmd)
        rollback_log.append(rollback_cmd)

    return rollback_log


'''dummy for the health checking via http'''
@activity.defn
async def verify_resolution(service: str) -> dict:

    logger.info(f"Verifying health for {service}")

    url = "http://mock-service:8080/health"

    async with httpx.AsyncClient() as client:

        response = await client.get(url)

        data = response.json()

    return {
        "service": service,
        "healthy": data["status"] == "healthy",
        "response": data,
    }


'''temporary postmortem report'''
@activity.defn
async def generate_postmortem(
    incident_id: str,
    classification: dict,
    plan: list[str],
    execution_results: list[dict],
    verification: dict,
    override_action: str | None,
) -> str:

    logger.info(f"Generating postmortem for {incident_id}")

    report = f"""
# Incident Postmortem

## Incident ID
{incident_id}

## Classification
Type: {classification["incident_type"]}

Severity: {classification["severity"]}

## Remediation Plan
"""

    for step in plan:
        report += f"- {step}\n"

    report += "\n## Execution Results\n"

    for result in execution_results:
        report += (
            f"- {result['command']} "
            f"-> {result['status']}\n"
        )

    report += f"""
## Verification

Healthy: {verification["healthy"]}

## Human Override

Override Action: {override_action}
"""

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    filepath = output_dir / f"postmortem-{incident_id}.md"

    with open(filepath, "w") as f:
        f.write(report)

    logger.info(f"Postmortem written to {filepath}")

    return str(filepath)