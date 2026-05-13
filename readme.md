# DevOps: Autonomous Incident Triage & Remediation Orchestrator


This project is an autonomous Dev-Ops system that classifies alerts, retrieves runbooks, generates remediation steps, and executes them against a mock Kubernetes cluster. 
Workflow automatically closes after 30 minutes- but allows human override.
The workflow verifies recovery, supports rollback handling, and generates automated postmortem reports from execution history.

## Running the code:

Go to directory root:
```
docker compose up --build
```
## Access the UI at:
```
http://localhost:3000
```
## To view Temporal workflow monitoring UI:
```
http://localhost:8081
```

## To monitor using Swagger UI:
```
http://localhost:8000/docs
```

### Environment Variables

This project uses the Groq API for LLM-powered incident classification, remediation planning, and postmortem generation.

Change the example `.env` file in the project root and add your own API key:

You can generate an API key from:
https://console.groq.com/keys














