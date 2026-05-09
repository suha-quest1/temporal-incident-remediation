# Incident Report — alert-oom-1778310567435

Date: 2026-05-09 07:09:29 UTC

Severity: P1
Issue Type: OOM

## Actions
- Run `kubectl top pods -n default` to identify resource-intensive pods
- Run `kubectl describe pod -l app=backend-api` to gather pod details
- Run `kubectl set resources deployment backend-api --limits=memory=512Mi` to adjust resource limits
- Run `kubectl rollout restart deployment/backend-api` to restart the deployment

## Result
- Identified pod `backend-api` as resource-intensive
- Adjusted resource limits for `backend-api` deployment
- Restarted `backend-api` deployment

## Follow-Up
- Monitor pod resource utilization
- Review deployment logs for errors

INCIDENT DATA:

Incident ID:
alert-oom-1778310567435

Timestamp:
2026-05-09 07:09:29 UTC

Incident Type:
OOM

Severity:
P1

Remediation Plan:
kubectl top pods -n default; kubectl describe pod -l app=backend-api; kubectl set resources deployment backend-api --limits=memory=512Mi; kubectl rollout restart deployment/backend-api

Execution Results:
kubectl top pods -n default->success; kubectl describe pod -l app=backend-api->success; kubectl set resources deployment backend-api --limits=memory=512Mi->success; kubectl rollout restart deployment/backend-api->success

Healthy After Fix:
True

Override Action:
rollback