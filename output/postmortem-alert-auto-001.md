# Incident Report — alert-auto-001

Severity: P1
Service Issue: OOM

## Actions
- Ran `kubectl top pods -n default` to identify the problematic pod
- Ran `kubectl describe pod -l app=backend-api` to gather more information
- Ran `kubectl set resources deployment backend-api --limits=memory=512Mi` to adjust resource limits
- Ran `kubectl rollout restart deployment/backend-api` to restart the deployment

## Result
- Successfully identified and mitigated the OOM issue
- Deployment was restarted and is now running within the new resource limits

## Follow-Up
- Conduct a review of the resource limits to prevent similar issues in the future
- Consider implementing monitoring to detect and alert on high memory usage
- Update the incident response plan to include OOM as a potential cause and the corresponding actions.