# Incident Report — alert-oom-1778227238901

Severity: P1
Service Issue: OOM

## Actions
- Ran `kubectl top pods -n default` to identify the issue
- Ran `kubectl describe pod -l app=backend-api` to gather more information
- Ran `kubectl set resources deployment backend-api --limits=memory=512Mi` to increase memory limits
- Ran `kubectl rollout restart deployment/backend-api` to restart the deployment

## Result
- Successfully increased memory limits and restarted the deployment
- Service is now operating within normal parameters

## Follow-Up
- Review and adjust memory limits for the deployment as necessary
- Consider implementing monitoring to prevent similar issues in the future