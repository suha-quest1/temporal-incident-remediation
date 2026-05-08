**Incident Postmortem: alert-demo-001**
=====================================

### Summary
On [Date], a critical incident (Severity: P1) occurred due to an Out of Memory (OOM) issue in the backend-api deployment in the default namespace. The incident was resolved within [Timeframe] through a series of corrective actions.

### Root Cause
The root cause of the incident was identified as a memory leak in the backend-api deployment, which was not properly configured to handle the increasing memory demands. The deployment's resource limits were not set, allowing the pods to consume excessive memory and eventually leading to an OOM error.

### Actions Taken
To resolve the incident, the following actions were taken:

1. **kubectl top pods -n default**: Verified the memory usage of the backend-api pods to confirm the OOM issue.
2. **kubectl describe pod -l app=backend-api**: Gathered additional information about the pod's status and resource usage.
3. **kubectl set resources deployment backend-api --limits=memory=512Mi**: Set a memory limit for the backend-api deployment to prevent future OOM issues.
4. **kubectl rollout restart deployment/backend-api**: Restarted the backend-api deployment to apply the new resource limits and resolve the incident.

### Verification
The incident was verified as resolved through the following means:

1. **kubectl top pods -n default**: Verified that the memory usage of the backend-api pods was within the configured limits.
2. **kubectl describe pod -l app=backend-api**: Confirmed that the pod's status and resource usage were stable.

### Lessons Learned
The following lessons were learned from this incident:

1. **Proper resource configuration**: Ensure that resource limits are set for deployments to prevent future OOM issues.
2. **Monitoring and alerting**: Implement robust monitoring and alerting mechanisms to detect memory usage anomalies and prevent similar incidents.
3. **Deployment restart**: Restarting the deployment can be an effective way to resolve incidents caused by resource limits or other configuration issues.