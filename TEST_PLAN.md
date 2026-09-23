# CISIA Emploi - Test Plan

This document lists the functional, integration, resilience and CI/CD tests for the M5-B1 architecture and feedback loop.

## 1. Static and Configuration Checks

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Compose syntax | `docker compose config` | Detect invalid YAML, interpolation or service configuration. | Exit code 0. |
| Retrain Compose profile | `docker compose --profile retrain config` | Verify that the optional retrainer service is valid. | Exit code 0. |
| Python compilation | `python -m py_compile scripts/retrain.py scripts/promotion.py` | Detect syntax errors before execution. | Exit code 0. |
| Diff validation | `git diff --check` | Detect whitespace errors. | No error. |
| Full pytest collection | `python -m pytest -q` | Verify that all maintained tests are collected without import conflicts. | All tests pass. |

## 2. Docker Architecture and Health

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Full startup | `docker compose up -d --build` | Verify that the complete stack starts from a clean build. | Services start successfully. |
| Service status | `docker compose ps` | Verify healthchecks and dependency order. | `model`, `backend` and `frontend` are healthy. |
| Model health | `Invoke-RestMethod http://localhost:8000/health` | Verify model liveness and artifact loading. | HTTP 200 and status `ok`. |
| Backend health | `Invoke-RestMethod http://localhost:8001/health` | Verify backend liveness. | HTTP 200 and status `ok`. |
| Frontend availability | `Invoke-WebRequest http://localhost:8088` | Verify Nginx serves the application. | HTTP 200 and HTML is returned. |
| Prometheus health | `Invoke-WebRequest http://localhost:9090/-/healthy` | Verify Prometheus is available. | HTTP 200. |
| Grafana health | `Invoke-WebRequest http://localhost:3001/api/health` | Verify Grafana is available. | HTTP 200. |
| Restart recovery | `docker compose restart model backend frontend` | Verify that services recover after restart. | Services become healthy again. |
| Feedback persistence | Submit a feedback, restart backend, query `/feedback/count`. | Verify that the SQLite volume survives container restarts. | The feedback remains present. |

## 3. Model API Contract

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Valid prediction | `POST http://localhost:8000/predict` with a valid CISIA payload. | Verify model inference with valid input. | HTTP 200. |
| Prediction class | Inspect `prediction`. | Verify multiclass output contract. | Value is `0`, `1` or `2`. |
| Probability keys | Inspect `probabilities`. | Verify all classes are represented. | Keys are `0`, `1`, `2`. |
| Probability sum | Sum all probability values. | Verify a valid probability distribution. | Sum is approximately `1.0`. |
| Model version | Inspect `model_version`. | Verify model provenance is returned. | Non-empty version. |
| Invalid age | Send `age=150` or `age=10`. | Verify Pydantic range validation. | HTTP 422. |
| Invalid diploma | Send an unsupported diploma value. | Verify enum validation. | HTTP 422. |
| Missing feature | Remove a required field. | Verify required-field validation. | HTTP 422. |
| Invalid target schema | Send malformed JSON. | Verify request parsing. | HTTP 422. |
| Model metrics | `Invoke-WebRequest http://localhost:8000/metrics` | Verify Prometheus endpoint. | HTTP 200 and model metrics are present. |

## 4. Backend Scoring and Orchestration

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Valid `/score` | `POST http://localhost:8001/score`. | Verify backend-to-model orchestration. | HTTP 200 and prediction response. |
| Request ID propagation | Send `X-Request-ID: REQ-TEST-001`. | Verify distributed request correlation. | Same ID is returned by backend and forwarded to model. |
| Request ID generation | Call `/score` without `X-Request-ID`. | Verify automatic ID generation. | A non-empty ID is returned. |
| Prediction ledger | Perform `/score`, then inspect feedback storage. | Verify raw input and prediction are recorded. | A row exists for the returned `request_id`. |
| Model unavailable | Stop model, then call `/score`. | Verify upstream availability handling. | HTTP 503. |
| Model error | Mock or force a model error response. | Verify upstream error mapping. | HTTP 502. |
| Backend metrics | `Invoke-WebRequest http://localhost:8001/metrics` | Verify HTTP and business instrumentation. | HTTP 200 with backend metrics. |
| Backend logs | `docker compose logs backend`. | Verify request ID and latency logging. | Request details are logged. |

## 5. Counselor Feedback API

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Valid feedback | POST `/feedback` with a known `request_id`. | Verify annotation storage. | HTTP 201 and `stored`. |
| Unknown request ID | Use a nonexistent `request_id`. | Prevent feedback from being attached to an unknown prediction. | HTTP 404. |
| Valid class 0 | Send `true_label=0`. | Verify first CISIA class. | HTTP 201. |
| Valid class 1 | Send `true_label=1`. | Verify second CISIA class. | HTTP 201. |
| Valid class 2 | Send `true_label=2`. | Verify critical-risk class. | HTTP 201. |
| Invalid class | Send `true_label=3` or `-1`. | Verify multiclass validation. | HTTP 422. |
| Prediction mismatch | Send a `prediction` different from the stored prediction. | Prevent inconsistent annotations. | HTTP 409. |
| Idempotent replay | Submit the exact same feedback twice. | Make network retries safe. | Second request returns `already_registered`; count does not increase. |
| Contradictory replay | Same ID with a different true label. | Detect conflicting human annotations. | HTTP 409. |
| Feedback count | `GET /feedback/count`. | Provide the retrain trigger input. | Returns total count and `new` count. |
| Feedback validation | Send missing or malformed fields. | Verify API schema validation. | HTTP 422. |

## 6. Frontend Counselor Workflow

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Score from UI | Fill the scoring form and submit. | Verify browser-to-backend scoring. | Prediction is displayed. |
| Display request ID | Inspect result panel. | Allow the counselor to identify the scored case. | Returned `request_id` is visible. |
| Feedback panel display | Complete a successful score. | Verify feedback UI activation. | Counselor panel appears after scoring. |
| Prediction prefill | Inspect true-result selector. | Reduce entry errors while allowing correction. | Predicted class is selected initially. |
| Corrected class | Select another true label and submit. | Verify human correction is possible. | Feedback is stored. |
| Comment submission | Enter a counselor comment. | Preserve useful context for retraining. | Comment reaches backend. |
| Duplicate protection | Submit feedback twice from the UI. | Prevent accidental repeated submissions. | Controls become disabled after success. |
| Feedback error display | Use an invalid or stale request ID. | Make backend failures visible to the counselor. | Clear error message is displayed. |

## 7. Prometheus and Grafana

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Model scrape | Open Prometheus targets or query the API. | Verify Prometheus can scrape the model. | Target `model` is `UP`. |
| Backend scrape | Open Prometheus targets or query the API. | Verify Prometheus can scrape the backend. | Target `backend` is `UP`. |
| Request counter | Send several scores and query `http_requests_total`. | Verify RPS data changes. | Counter increases. |
| Latency histogram | Send scores and query duration buckets. | Verify p50/p95/p99 data exists. | Histogram samples appear. |
| HTTP error metrics | Send invalid requests or stop model. | Verify errors are observable. | 4xx/5xx series increase. |
| Business class metrics | Send predictions of different classes. | Verify predicted-class distribution. | Business counters increase by class. |
| Upstream error metric | Stop model and call backend. | Verify model dependency failures are measured. | `backend_model_upstream_errors_total` increases. |
| Grafana availability panel | Open dashboard and inspect `Vie`. | Answer whether services are alive. | Model/backend status and errors are visible. |
| Grafana speed panel | Inspect `Vitesse`. | Answer whether the service is fast enough. | p50/p95/p99 panels contain data. |
| Grafana behavior panel | Inspect `Comportement`. | Answer whether predictions behave normally. | Class distribution and confidence are visible. |
| Model version panel | Inspect deployed model panel. | Verify deployed artifact traceability. | Model name/version is visible. |

## 8. Evaluation and Quality Gate

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Nominal evaluation | `python scripts/evaluate_model.py --release-tag test` | Evaluate production on the frozen reference set. | Exit code 0 and `violations: []`. |
| Degraded evaluation | `python scripts/evaluate_model.py --release-tag degraded --degrade` | Prove that a degraded model is blocked. | Exit code 1 and failed status. |
| Reference validation | Run evaluation with an invalid or incomplete reference set. | Prevent unreliable quality gates. | Clear error and non-zero exit. |
| Golden baseline | `python scripts/evaluate_model.py --freeze-baseline`. | Freeze the reference metrics used for comparison. | Baseline JSON is written. |
| MLflow tracking | Inspect the MLflow run after evaluation. | Verify reproducible evaluation history. | Metrics and release tag are recorded. |

## 9. Retraining Trigger

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| No feedback | `docker compose --profile retrain run --rm retrainer`. | Verify the trigger does not train without feedback. | Skip message; no candidate. |
| Below threshold | Run with 199 unconsumed feedbacks and `--min-feedback 200`. | Verify threshold protection. | Skip; no training. |
| Exact threshold | Run with 200 unconsumed feedbacks. | Verify trigger boundary. | Training starts. |
| Manual trigger | `./scripts/run_retrain.ps1 -MinFeedback 200`. | Verify operator-triggered retraining. | Retrainer executes. |
| Scheduled trigger | Run the GitHub Actions `retrain.yml` schedule. | Verify scheduled automation. | Workflow starts and uploads result artifacts. |
| Workflow dispatch | Run the retraining workflow from the GitHub Actions interface. | Verify manual CI trigger without branch-specific commands. | Workflow is accepted and starts. |
| Missing CI database | Run workflow without `data/feedbacks.db`. | Make the persistence limitation explicit. | Workflow skips safely with a warning. |
| Incomplete feedback | Add a prediction with missing CISIA fields. | Prevent malformed training data. | Clear error; feedback is not silently consumed. |
| Failed training | Force a preprocessing or model error. | Verify transactional behavior. | Feedback remains unconsumed. |
| Consumed feedback | Complete a successful retrain. | Avoid retraining repeatedly on identical data. | Used feedbacks are marked consumed. |

## 10. Candidate Evaluation and Promotion

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Candidate artifact | Run successful retrain. | Verify candidate persistence. | Candidate `.joblib` and `.json` exist. |
| Three-class contract | Inspect candidate probabilities. | Verify candidate compatibility with CISIA. | Three finite probabilities in `[0,1]`. |
| Same reference set | Compare candidate and production on `reference_set.csv`. | Ensure fair model comparison. | Both use identical observations. |
| Quality floor failure | Use metrics below a configured floor. | Block unsafe candidates. | Promotion rejected. |
| Class 2 regression | Candidate recall class 2 drops beyond tolerance. | Protect the critical business class. | Promotion rejected. |
| No improvement | Candidate is equal or worse. | Avoid unnecessary redeployments. | Promotion rejected. |
| Candidate improvement | Candidate improves required metrics. | Verify positive promotion path. | Promotion accepted. |
| Decision journal | Inspect `decisions_log.jsonl`. | Provide auditability. | Every decision has metrics and reason. |
| Rejected candidate | Run a rejected promotion. | Verify no unsafe artifact is promoted. | No promoted artifact is created or changed. |
| Promoted candidate | Run an accepted promotion. | Verify deployable artifact creation. | Promoted joblib and metadata exist. |

## 11. Promoted Model Deployment and Rollback

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Missing promoted artifact | `./scripts/deploy_promoted.ps1`. | Prevent deployment of an incomplete promotion. | Command fails clearly. |
| Promoted deployment | `./scripts/deploy_promoted.ps1 -Build`. | Load the accepted artifact in Docker. | Model/backend/frontend are recreated and healthy. |
| Artifact selection | Inspect `MODEL_ARTIFACT` and `/info`. | Verify the intended model is loaded. | Promoted version is reported. |
| Prediction after deployment | Call `/score` after deployment. | Verify serving compatibility. | HTTP 200 with three probabilities. |
| Restart promoted model | Restart `model` and query `/info`. | Verify artifact persistence. | Same promoted version is loaded. |
| Rollback | Remove `MODEL_ARTIFACT` override and restart Compose. | Return to the stable default artifact. | Default production version is loaded. |
| Missing model artifact | Point `MODEL_ARTIFACT` to a nonexistent file. | Verify startup failure is visible. | Model becomes unhealthy or exits. |

## 12. CI/CD Pipeline

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Pull request | Open a PR. | Verify lint, tests, contract test and evaluation. | CI passes for valid changes. |
| Contract failure | Intentionally break the model contract in a temporary test change. | Verify release protection. | CI fails before image publication. |
| Quality-gate failure | Run the degraded evaluation path in a temporary test change. | Verify degraded models cannot be released. | Build/push jobs are blocked. |
| Main push | Push to `main`. | Verify image build and GHCR publication. | `model`, `backend` and `frontend` images are pushed. |
| Release tag | Push a `v*` tag. | Verify release publication path. | Images receive the release tag and GitHub Release is created. |
| Retrain workflow | Run the retraining workflow from the GitHub Actions interface. | Verify remote retrain dispatch. | Workflow is found and starts. |
| Artifact upload | Inspect workflow artifacts. | Preserve retrain result and model artifacts. | Logs, decisions and candidates are available. |

## 13. Resilience and Concurrency

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Concurrent duplicate feedback | Submit the same feedback from two clients simultaneously. | Verify primary-key/idempotency behavior. | One stored result; no corrupted row. |
| Concurrent contradictory feedback | Submit different labels for the same ID simultaneously. | Detect annotation conflicts. | One accepted; the other returns conflict. |
| Concurrent retrainers | Start two retrainers at once. | Prevent duplicate promotion or inconsistent consumption. | Concurrency policy blocks or serializes runs. |
| Restart during retrain | Restart backend while retrainer runs. | Verify feedback database durability. | No silent data loss. |
| Interrupted training | Stop retrainer during fit. | Verify incomplete candidate is not deployed. | Production artifact remains unchanged. |
| Empty reference set | Replace reference set with an empty file in a test copy. | Prevent meaningless promotion. | Evaluation fails clearly. |
| Missing metadata | Remove model metadata in a test copy. | Verify startup/evaluation failure is explicit. | Service or gate fails safely. |
| Unknown categorical value | Score a new ROME code. | Verify preprocessing handles unseen categories. | Request does not fail solely due to the new category. |
| Empty text | Score an empty interview summary if schema permits. | Verify text preprocessing behavior. | Predictable validation or fallback behavior. |
| INSEE edge cases | Test leading zeroes, `2A` and `2B`. | Verify department feature extraction. | Correct department handling. |

## 14. Recommended End-to-End Demonstration

Run this sequence for a complete proof of the architecture:

1. `docker compose up -d --build`
2. Verify all healthchecks with `docker compose ps`.
3. Submit a valid score through the frontend or backend.
4. Capture the returned `request_id`.
5. Submit a counselor feedback with that ID.
6. Verify `/feedback/count`.
7. Accumulate or simulate the configured feedback threshold.
8. Run the retrainer.
9. Verify candidate creation.
10. Evaluate candidate and production on the same reference set.
11. Inspect `decisions_log.jsonl`.
12. Verify promotion or rejection.
13. Deploy the promoted artifact if accepted.
14. Verify `/info`, `/score`, Prometheus and Grafana.
15. Perform a rollback test.
16. Run `python -m pytest -q` and confirm all tests pass.
