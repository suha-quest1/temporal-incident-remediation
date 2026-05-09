# Incident Report — alert-oom-1778312168084

Date: 2026-05-09 07:36:13 UTC

Severity: P1
Issue Type: OOM

## Actions
- Approved override action
- Ran `kubectl top pods -n default` to identify resource usage
- Ran `kubectl describe pod -l app=backend-api` to gather pod details
- Ran `kubectl set resources deployment backend-api --limits=memory=512Mi` to adjust resource limits
- Ran `kubectl rollout restart deployment/backend-api` to restart deployment

## Result
- Deployment backend-api restarted successfully
- Resource limits adjusted to 512Mi

## Follow-Up
- Monitor pod resource usage
- Review deployment logs for errors