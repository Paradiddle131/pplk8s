# Runbook

Operational entries for the lab, grown phase by phase.
Every command uses the `kind-pplk8s` context and the `workloads` namespace; `K` below stands for `kubectl --context kind-pplk8s -n workloads`.

## Phase 2 drills

Each drill breaks the healthy EL Factory Deployment on purpose, using a `kubectl patch` or `kubectl set image` against the live object.
The symptoms below were observed on Kubernetes 1.36.4 (kind) with the manifests in `platform/k8s/workloads/`.
Every drill is undone the same way: re-apply the manifests with `platform/k8s/workloads-up.sh`, which restores the declared state.
(`kubectl rollout undo` also works, but it returns to the previous revision, which is the broken one if you drilled twice in a row.)

General triage order for any pod problem:

```bash
K="kubectl --context kind-pplk8s -n workloads"
$K get pods -o wide                          # STATUS column names the failure class
$K describe pod <pod>                        # State / Last State / Events at the bottom
$K logs <pod> [--previous]                   # --previous reads the last crashed container
$K get events --sort-by=.lastTimestamp       # namespace-wide timeline
```

One property shows up in every drill: the Deployment uses `maxUnavailable: 0`, so a bad rollout leaves the two old pods Running and serving the Service while the new pod fails.
`kubectl rollout status` then times out instead of the service going down.

### 1. Bad image tag (ImagePullBackOff)

Trigger:

```bash
$K set image deployment/el-factory el-factory=localhost:5001/el-factory:9.9.9
```

Symptom: the new pod's STATUS goes `ErrImagePull`, then `ImagePullBackOff`.
`kubectl rollout status` stalls with `Waiting for deployment "el-factory" rollout to finish: 1 out of 2 new replicas have been updated...` and then times out.
The two old pods stay `1/1 Running`.

Diagnosis (`describe pod` events):

```
Normal   Pulling  kubelet  Pulling image "localhost:5001/el-factory:9.9.9"
Warning  Failed   kubelet  Failed to pull image "localhost:5001/el-factory:9.9.9": rpc error: code = NotFound desc = failed to pull and unpack image "localhost:5001/el-factory:9.9.9": failed to resolve reference "localhost:5001/el-factory:9.9.9": localhost:5001/el-factory:9.9.9: not found
Warning  Failed   kubelet  Error: ErrImagePull
Normal   BackOff  kubelet  Back-off pulling image "localhost:5001/el-factory:9.9.9"
Warning  Failed   kubelet  Error: ImagePullBackOff
```

`not found` means the registry answered but has no such tag.
A connection error instead would point at the registry or the node's containerd mirror config.
Check what the registry holds with `curl -s localhost:5001/v2/el-factory/tags/list`.

Fix: use a tag that exists (`make push` publishes `0.1.0`), then `workloads-up.sh`.

### 2. Failing probe

Two variants, which behave differently.

**Readiness probe fails** (the app is fine, the probe asks the wrong question):

```bash
$K patch deployment el-factory --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/nope"}]'
```

Symptom: the new pod stays `0/1 Running` with `RESTARTS 0`, and the Deployment shows `READY 2/2  UP-TO-DATE 1` because the old pods still serve.
The Service's EndpointSlice lists the new pod's address with `ready=false`, so it receives no traffic.

```
Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe failed with statuscode: 404
```

The probe line in `describe pod` shows the cause: `Readiness: http-get http://:http/nope ...`.
Readiness never restarts a container; it only gates traffic.

**Startup (or liveness) probe fails** (the kubelet kills the container):

```bash
$K patch deployment el-factory --type=json -p '[
  {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/nope"},
  {"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/httpGet/path","value":"/nope"},
  {"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/failureThreshold","value":3}]'
```

Symptom: the new pod climbs through `RESTARTS 1, 2, ...` and ends in `CrashLoopBackOff`.

```
Warning  Unhealthy  kubelet  Startup probe failed: HTTP probe failed with statuscode: 404
Normal   Killing    kubelet  Container el-factory failed startup probe, will be restarted
Warning  BackOff    kubelet  Back-off restarting failed container el-factory in pod ...
```

`kubectl logs` shows the probe's requests in the gunicorn access log (`GET /nope ... 404 ... "kube-probe/1.36"`), then `Handling signal: term` when the kubelet stops it.
Telltale difference from a real crash: the app log is healthy and ends with a SIGTERM, and the exit is a kill, not an error.

Fix: restore the probe path with `workloads-up.sh`.

### 3. OOMKill (memory limit too tight)

Trigger (requests must not exceed limits, or the API rejects the patch with `resources.requests: Invalid value: "128Mi": must be less than or equal to memory limit of 20Mi`):

```bash
$K patch deployment el-factory --type=json -p '[
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"20Mi"},
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"16Mi"}]'
```

Symptom: the new pod restarts within a second of each start and ends in `CrashLoopBackOff`.
`describe pod` is the diagnosing command:

```
State:          Waiting
  Reason:       CrashLoopBackOff
Last State:     Terminated
  Reason:       OOMKilled
  Exit Code:    137
Limits:
  memory:  20Mi
```

Exit code 137 is 128 + SIGKILL(9); the reason `OOMKilled` says the kernel's cgroup killed it for exceeding the limit.
`kubectl logs --previous` shows only the gunicorn start-up lines (`Starting gunicorn`, `Listening at`) and then nothing: the process is killed with no error message, which is why logs alone mislead.
Also visible: `Startup probe failed: ... connection refused`, because the app never finishes starting.
`kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'` returns `"reason":"OOMKilled","exitCode":137`.

Fix: raise the limit (the manifest says 256Mi) by re-applying with `workloads-up.sh`.
Size the limit from observed usage; the lab has no metrics-server, so raise it step by step.

### 4. Missing Secret (CreateContainerConfigError)

Trigger (a typo in the Secret name, the common real-world cause):

```bash
$K patch deployment el-factory --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/envFrom/1/secretRef/name","value":"warehouse-credential"}]'
```

Symptom: the new pod's STATUS is `CreateContainerConfigError` with `RESTARTS 0`; the container is never created, so there are no logs at all.

```
State:          Waiting
  Reason:       CreateContainerConfigError
Warning  Failed  kubelet  Error: secret "warehouse-credential" not found
```

The image pull succeeded (`Pulled` events repeat), and the kubelet then fails resolving `envFrom`.
Diagnosis commands: `$K describe pod <pod>` for the exact missing name, then `$K get secret` to compare with what exists (`warehouse-credentials`, 6 keys).
`kubectl logs` has nothing to show because the container was never created.

Fix: correct the reference, or create the Secret; the kubelet retries on its own and the pod starts without a restart of the Deployment.
Here, `workloads-up.sh` restores both the Secret and the reference.
The same error appears for a missing ConfigMap or a missing key referenced through `secretKeyRef`.

### Restoring the healthy state

```bash
platform/k8s/workloads-up.sh
$K get pods -l app.kubernetes.io/name=el-factory     # 2 pods, 1/1 Running
make phase2-check
```
