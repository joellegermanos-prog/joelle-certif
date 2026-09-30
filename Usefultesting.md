# CISIA Emploi - Test Plan

This document lists the functional, integration, resilience and CI/CD tests for the M5-B1 architecture and feedback loop.

## 1. Static and Configuration Checks

| Test | Command / action | Purpose | Expected result |
|---|---|---|---|
| Compose syntax | `docker compose config` | Detect invalid YAML, interpolation or service configuration. | Exit code 0. |
| Retrain Compose profile | `docker compose --profile retrain config` | Verify that the optional retrainer service is valid. | Exit code 0. |
| Python compilation | `python -m py_compile scripts/retrain.py scripts/promotion.py` | Detect syntax errors before execution. | Exit code 0. |
| Calibration compilation | `python -m py_compile src/calibration.py src/recommendations.py` | Verify the calibration and recommendation modules compile. | Exit code 0. |
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
| Invalid seniority | Send `anciennete_poste_ans=-1`. | Verify Pydantic range validation. | HTTP 422. |
| Optional age | Send a payload without `age`. | Verify the ethical model does not require age. | HTTP 200. |
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

## 15. Analyse de dérive et diagnostic

Le script `scripts/drift_analysis.py` compare un échantillon de référence et
un échantillon courant ayant le même schéma de features. Il calcule :

- le PSI sur les variables numériques et les probabilités ;
- le test de Kolmogorov-Smirnov sur les variables numériques ;
- le test du Chi² sur les variables catégorielles ;
- la relation feature-cible dans chaque période lorsque les labels courants
	sont disponibles ;
- un indicateur d'alerte destiné aux panels Grafana.

Exemple :

```powershell
python scripts/drift_analysis.py `
	--reference data/reference_set.csv `
	--current data/current_scored.csv `
	--output reports/drift.json `
	--prometheus-output reports/drift.prom
```

Interprétation recommandée :

| Signal | Interprétation | Action |
|---|---|---|
| PSI >= 0,25 | Changement important de distribution d'une entrée ou d'une probabilité | Vérifier la période, la source et la population avant décision |
| KS p-value < 0,05 | Changement statistiquement significatif d'une variable numérique | Contrôler les volumes, valeurs manquantes et modalités |
| Chi² p-value < 0,05 | Changement statistiquement significatif d'une variable catégorielle | Vérifier les changements métier ou de collecte |
| Relation feature-cible modifiée | Signal de concept drift si les labels courants sont fiables | Comparer les erreurs par classe et envisager un retrain contrôlé |
| PSI des probabilités élevé | Dérive de confiance/calibration potentielle | Vérifier la calibration, la population et les seuils d'escalade |

Les panels 18 à 21 du dashboard Grafana étendent la supervision existante
avec le PSI, les p-values KS/Chi², la dérive des probabilités et le statut de
triangulation. Le rapport doit être croisé avec :

- le contexte métier : changement de dispositif, public ou règles de collecte ;
- le contexte temporel : date de mise en production, saisonnalité et fenêtre
	d'observation ;
- la qualité des labels : délai d'annotation, volume et taux de feedback ;
- les métriques système : latence, erreurs et versions déployées.

Un drift statistique seul ne justifie pas une promotion. La décision finale
doit distinguer data drift et concept drift, puis passer par l'évaluation sur
le jeu de référence et la politique de promotion.

## 16. Fonctionnement complet de la logique

Cette section explique le rôle des composants et la raison de leur présence.

### 15.1 Architecture générale

Le projet suit le flux suivant :

```text
Navigateur
		|
		v
Frontend Nginx :8088
		| /api/score et /api/feedback
		v
Backend FastAPI :8001
		| /predict
		v
Model FastAPI :8000
		|
		+--> Prometheus :9090 --> Grafana :3001
		|
		+--> registre SQLite des prédictions et feedbacks
```

Cette séparation évite de mélanger l'interface utilisateur, l'orchestration
HTTP et le calcul du modèle. Le frontend ne charge jamais le modèle. Le
backend valide et transmet les requêtes. Le service model est responsable de
charger le pipeline et de produire une prédiction.

### 15.2 `docker-compose.yml`

- `model` construit l'image du service de prédiction et expose le port `8000`.
- `backend` construit l'orchestrateur FastAPI et expose le port `8001`.
- `frontend` construit l'image Nginx et expose l'application sur `8088`.
- `prometheus` collecte les métriques des services model et backend.
- `grafana` affiche les métriques Prometheus dans le dashboard provisionné.
- `retrainer` est un service optionnel activé avec le profil `retrain`.

Les `depends_on` et les healthchecks imposent l'ordre de démarrage : le
backend attend que le modèle soit sain, puis le frontend attend que le
backend soit sain. Le volume `feedback_data` conserve SQLite lorsque le
conteneur backend est redémarré.

### 15.3 Frontend et scoring

Le fichier `services/frontend/html/index.html` contient le formulaire de
demande d'emploi. Après soumission :

1. le navigateur construit le payload CISIA ;
2. il appelle `/api/score` ;
3. Nginx transmet `/api/score` au backend ;
4. le backend appelle `/predict` sur le service model ;
5. la réponse contient la classe, les probabilités, la version du modèle et
	 le `request_id` ;
6. le frontend affiche la prédiction et conserve le `request_id` pour le
	 formulaire conseiller.

Le `request_id` est essentiel : il relie la prédiction à son résultat réel
ultérieur. Sans cet identifiant, un feedback pourrait être attribué au
mauvais dossier.

### 15.4 Service model

`services/model/app/main.py` charge au démarrage :

- le fichier modèle Joblib ;
- le fichier JSON de métadonnées ;
- la version et l'identité du modèle dans la métrique `cisia_model_info`.

Le chemin peut être changé avec `MODEL_ARTIFACT`. Cela permet de charger le
modèle standard ou un artefact promu sans modifier le code du service.

La route `POST /predict` :

1. valide les champs avec Pydantic ;
2. applique `create_features` ;
3. appelle `predict` et `predict_proba` ;
4. traduit la classe en libellé métier ;
5. enregistre les métriques de comportement ;
6. retourne trois probabilités correspondant aux classes CISIA `0`, `1` et `2`.

La route `POST /train` existe aussi pour un réentraînement contrôlé par API.
Elle entraîne une copie du modèle, journalise les métriques dans MLflow et
remplace le modèle en mémoire du processus. Le retrain industrialisé décrit
plus loin utilise cependant `scripts/retrain.py` afin de produire un candidat
et de passer par une évaluation avant promotion.

### 15.5 Backend et registre de prédictions

`services/backend/app/main.py` est l'orchestrateur exposé au frontend.

La route `POST /score` :

1. valide la demande avec `EmploymentApplication` ;
2. génère ou reprend `X-Request-ID` ;
3. appelle `MODEL_URL/predict` ;
4. traduit une indisponibilité modèle en `503` et une erreur upstream en `502` ;
5. enregistre l'entrée et la réponse dans la table `predictions` ;
6. retourne la réponse au navigateur.

Le registre conserve les features brutes, la classe prédite, les probabilités,
la version du modèle et la date. Il est nécessaire pour reconstruire plus
tard les observations annotées utilisées par le réentraînement.

### 15.6 Feedback conseiller

Après un scoring réussi, le frontend affiche le `request_id` et un formulaire
de confirmation du résultat réel. Le conseiller sélectionne la classe
observée et peut ajouter un commentaire.

La route `POST /feedback` vérifie :

- que le `request_id` existe dans `predictions` ; sinon `404` ;
- que la prédiction envoyée correspond à celle enregistrée ; sinon `409` ;
- que le label appartient à `{0, 1, 2}` ; sinon `422` ;
- qu'un rejeu identique est idempotent ;
- qu'un même dossier avec deux labels différents est refusé avec `409`.

La table `feedbacks` contient aussi `used_for_training`. Cette colonne permet
de compter uniquement les nouveaux feedbacks et évite de réutiliser
indéfiniment les mêmes a
nnotations.

### 15.7 Base SQLite et limite GitHub Actions

`data/feedbacks.db` est une base d'exécution et est ignorée par Git. En local,
le backend utilise `/app/data/feedbacks.db`, monté dans le volume Docker
`feedback_data`.

`scripts/init_feedback_db.py` crée uniquement les tables et les contraintes.
Il ne fabrique pas de faux labels : un feedback doit venir d'une annotation
réelle du conseiller.

Le runner GitHub Actions est une machine éphémère et ne voit pas le volume
Docker local. Le workflow `retrain.yml` initialise donc une base vide sur le
runner, puis affiche `Skip retrain` tant qu'aucune base contenant des
feedbacks réels n'est fournie. Pour un retrain distant réel, il faut importer
la base depuis un stockage persistant ou utiliser une base de données
accessible au runner.

### 15.8 `scripts/retrain.py`

Le script est le moteur de la boucle de feedback locale ou CI :

1. lit les feedbacks non consommés dans SQLite ;
2. compare leur nombre à `--min-feedback` ;
3. s'arrête proprement si le seuil n'est pas atteint ;
4. joint chaque feedback à l'entrée originale de `predictions` ;
5. ajoute les lignes annotées au dataset historique CISIA, après retrait du
   holdout de référence et des feedbacks qui rejouent une ligne de
   `reference_set.csv` ;
6. applique le preprocessing multimodal existant ;
7. entraîne une pipeline XGBoost multiclasses ;
8. vérifie que le candidat produit trois probabilités finies ;
9. écrit un artefact candidat séparé ;
10. évalue le candidat et la production sur le même jeu de référence ;
11. demande une décision à `scripts/promotion.py` ;
12. journalise toujours la décision ;
13. écrit un artefact promu uniquement si la décision est positive ;
14. marque les feedbacks comme consommés après le traitement réussi.

Le seuil répond à la question « quand réentraîner ? ». Il ne répond pas à la
question « faut-il déployer ? » : cette seconde question est traitée par la
policy de promotion.

### 15.9 Évaluation et promotion

Le candidat et le modèle de production sont comparés sur le même
`data/reference_set.csv`. Les métriques suivies sont notamment :

- accuracy ;
- F1 macro ;
- F1 de la classe 2 ;
- recall de la classe 2 ;
- précision de la classe 2 ;
- ROC-AUC multiclasses.

La classe `2` représente le risque de chômage longue durée et constitue la
métrique métier critique. La promotion est refusée si :

- un plancher de qualité n'est pas atteint ;
- une régression dépasse la tolérance ;
- le candidat n'apporte pas de gain suffisant.

Une décision acceptée produit `cisia_emploi_promoted.joblib` et ses
métadonnées. Une décision rejetée est normale : elle est journalisée mais ne
doit pas remplacer le modèle stable.

### 15.10 Déploiement d'un modèle promu

`MODEL_ARTIFACT` permet au service model de choisir l'artefact chargé au
démarrage. Les scripts `deploy_promoted.ps1` et `deploy_promoted.sh` :

1. vérifient la présence du Joblib et du JSON promus ;
2. définissent le chemin de l'artefact ;
3. recréent model, backend et frontend ;
4. vérifient l'état des conteneurs.

Si l'artefact promu est absent, le déploiement s'arrête plutôt que de lancer
un service dans un état ambigu. Le modèle standard reste le fallback.

### 15.11 CI/CD

`ci.yml` valide et publie le logiciel :

```text
lint
	-> tests
	-> contract-tests
	-> model-evaluation
	-> build des trois images
	-> push GHCR
	-> GitHub Release pour un tag v*
```

`retrain.yml` est séparé car il répond à un autre événement : l'arrivée de
feedbacks. Il déclenche le retrain selon un calendrier ou manuellement. Les
deux workflows ne se déclenchent pas automatiquement l'un l'autre dans la
configuration actuelle. La promotion locale peut être déployée avec le
script dédié ; l'automatisation distante complète nécessite de rendre la base
de feedback accessible au runner et de relier ensuite la promotion au
pipeline de publication.

### 15.12 Pourquoi les tests sont nécessaires

Chaque couche protège un risque différent :

- les tests de schéma protègent les entrées invalides ;
- les contract tests protègent le format du modèle ;
- les tests backend protègent l'orchestration et le `request_id` ;
- les tests feedback protègent la qualité des annotations ;
- les tests de seuil évitent les entraînements trop fréquents ;
- les tests de promotion évitent de déployer une régression ;
- les tests Docker vérifient le démarrage réel des services ;
- les tests Prometheus/Grafana vérifient l'observabilité ;
- les tests CI vérifient que le code validé est bien celui publié.

La chaîne complète est donc :

```text
score
	-> request_id
	-> feedback conseiller
	-> stockage SQLite
	-> seuil de nouveaux feedbacks
	-> candidat CISIA
	-> évaluation commune
	-> promotion ou rejet
	-> artefact promu
	-> déploiement contrôlé
	-> métriques et rollback
```

## 17. Calibration, drift et recommandation

Cette partie complète le flux opérationnel avec une mesure explicite de la
fiabilité des probabilités. Elle ne remplace pas `scripts/drift_analysis.py` :
les deux composants répondent à des questions différentes.

### 17.1 Chemin de calcul

```text
reference/current : probabilités + labels arrivés à maturité
	-> calibration.reliability_table()
	-> calibration.expected_calibration_error()
	-> comparaison ECE référence/current
	-> calibration_degraded()
	-> DriftDiagnosis(n_features_drift, auc_stable,
	                  calibration_degraded, f1_drop)
	-> diagnose_drift_type()
	-> recommend()
```

Le module `src/calibration.py` fonctionne ainsi :

1. `_calibration_frame()` aligne les probabilités et labels, supprime les
	 valeurs manquantes, vérifie que les probabilités sont dans `[0, 1]` et que
	 les labels valent `0` ou `1`.
2. Les probabilités sont découpées en intervalles fixes avec
	 `n_bins` classes sur `[0, 1]`. Le même binning doit être utilisé pour deux
	 périodes comparées.
3. `reliability_table()` calcule, pour chaque bin non vide, le nombre de cas,
	 la confiance moyenne, le taux réellement observé et l'écart
	 `confiance_moyenne - taux_observe`.
4. `expected_calibration_error()` calcule la moyenne pondérée des écarts
	 absolus. Un ECE plus élevé signifie une calibration plus dégradée, mais ne
	 montre pas à lui seul dans quel bin l'erreur se situe.
5. `calibration_degraded()` compare l'ECE courant à celui de référence et
	 renvoie `True` si l'augmentation dépasse `min_increase`. Si une période ne
	 contient aucune observation exploitable, le résultat est `False` plutôt que
	 de produire un verdict artificiel.

### 17.2 Rôle du script de drift

`scripts/drift_analysis.py` produit un rapport JSON et, si demandé, des
métriques Prometheus. `analyse()` calcule :

- PSI et KS pour `anciennete_poste_ans` (l'âge n'est plus collecté ni utilisé par le modèle) ;
- Chi² pour `niveau_diplome`, `code_rome_vise` et `code_insee_commune` ;
- les relations feature-cible dans les deux périodes lorsque
	`classe_retour_emploi` est disponible ;
- le PSI et KS des probabilités `proba_0`, `proba_1`, `proba_2`.

Le PSI des probabilités est un signal de déplacement de confiance, pas un
ECE. L'ECE exige les vrais labels et doit donc être calculé en différé sur une
fenêtre dont les labels sont suffisamment mûrs. La décision ne doit pas être
prise à partir d'un seul PSI, KS, Chi² ou ECE : elle croise distribution,
performance, calibration, temporalité et qualité des labels.

Commande de production du rapport :

```powershell
python scripts/drift_analysis.py `
	--reference data/reference_set.csv `
	--current data/current_scored.csv `
	--output reports/drift.json `
	--prometheus-output reports/drift.prom
```

### 17.3 Passage à la recommandation

`DriftDiagnosis` est le contrat entre les mesures et la décision :

- `n_features_drift > 0` signifie qu'au moins une feature dépasse le seuil
	PSI de la politique de diagnostic ;
- `auc_stable` indique que le pouvoir de classement reste dans la tolérance ;
- `calibration_degraded` vient de `calibration_degraded()` et décrit la
	fiabilité des probabilités, pas le choix d'un seuil métier ;
- `f1_drop` est la baisse de F1 macro entre les périodes comparées.

`diagnose_drift_type()` fournit une hypothèse :

| Features | AUC | Type retourné |
|---|---|---|
| dérivent | stable | `data drift` |
| stables | instable | `concept drift` |
| dérivent | instable | `mixte` |
| stables | stable | `pas de signal` |

`recommend()` applique ensuite la politique métier :

- concept drift, ou mixte avec baisse F1 supérieure à `0.03` : réentraîner en
	urgence et investiguer ;
- data drift avec calibration dégradée ou baisse F1 supérieure à `0.03` :
	réentraîner sur données récentes sous trois semaines ;
- data drift sans impact performance/calibration : surveiller ;
- mixte sous la tolérance : ajuster le seuil et renforcer la surveillance ;
- aucun signal : maintenir la surveillance.

Cette fonction formule une recommandation, mais ne lance pas le réentraînement
et ne promeut aucun modèle. Le déclenchement réel est séparé dans
`scripts/retrain.py`, protégé par le nombre de feedbacks non consommés.

### 17.4 Tests spécifiques

| Test | Commande | Résultat attendu |
|---|---|---|
| Calibration parfaite | `pytest -q tests/test_smoke.py -k calibration_ece` | ECE nul et colonnes du reliability table présentes. |
| Calibration dégradée vers recommandation | `pytest -q tests/test_smoke.py -k calibration_degraded` | ECE courant supérieur, `data drift`, réentraînement recommandé. |
| Drift statistique | `pytest -q tests/test_drift_analysis.py` | PSI, KS, Chi² et triangulation retournent leur contrat. |
| Rapport CLI | `python scripts/drift_analysis.py --reference ... --current ... --output reports/drift.json` | JSON écrit, valeurs non finies sérialisées en `null`. |
| Suite locale | `python -m pytest -q` | Tous les tests collectés passent ; les fixtures nécessaires doivent être présentes. |

Un test de calibration ne doit pas dépendre d'un modèle entraîné ni d'un
service Docker : il utilise de petites séries déterministes. Les tests
d'intégration Docker restent nécessaires pour vérifier que les métriques
Prometheus, le scoring et le feedback fonctionnent ensemble.

## 18. Commandes PowerShell prêtes à l'emploi

Commandes concrètes pour exécuter les sections 2 à 11 depuis `certification/`,
avec le `.venv` activé. Le modèle servi par défaut est
`cisia_emploi_xgboost_multimodal_ethique_best_class_2_ethique`.

### 18.1 Vérification du modèle chargé

```powershell
Invoke-RestMethod http://localhost:8000/info   # scénario multimodal_ethique attendu
```

### 18.2 Scoring valide et contrôles d'erreur

```powershell
$body = @{
  niveau_diplome = "Bac+2"; anciennete_poste_ans = 3
  code_rome_vise = "M1805"; est_allocataire = 0; code_insee_commune = "75056"
  synthese_entretien = "Recherche un emploi stable dans l'informatique."
} | ConvertTo-Json
$r = Invoke-RestMethod http://localhost:8001/score -Method Post -Body $body `
  -ContentType "application/json; charset=utf-8" -Headers @{ "X-Request-ID" = "REQ-TEST-001" }
$r
($r.probabilities.PSObject.Properties.Value | Measure-Object -Sum).Sum   # ≈ 1

# Ancienneté négative -> 422
$bad = $body | ConvertFrom-Json ; $bad.anciennete_poste_ans = -1
try { Invoke-RestMethod http://localhost:8001/score -Method Post -Body ($bad | ConvertTo-Json) -ContentType "application/json" } `
catch { $_.Exception.Response.StatusCode.value__ }

# Modèle indisponible -> 503
docker compose stop model
try { Invoke-RestMethod http://localhost:8001/score -Method Post -Body $body -ContentType "application/json" } `
catch { $_.Exception.Response.StatusCode.value__ }
docker compose start model
```

### 18.3 Feedback conseiller

```powershell
$fb = @{ request_id = $r.request_id; prediction = $r.prediction; true_label = 2; comments = "test" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8001/feedback -Method Post -Body $fb -ContentType "application/json"   # 201 stored
Invoke-RestMethod http://localhost:8001/feedback -Method Post -Body $fb -ContentType "application/json"   # already_registered
Invoke-RestMethod http://localhost:8001/feedback/count
```

Variantes : `request_id` inconnu -> `404`, `true_label = 3` -> `422`,
`prediction` différente de celle enregistrée -> `409`.

### 18.4 Quality gate

```powershell
python scripts/evaluate_model.py --release-tag test               # exit 0, violations: []
python scripts/evaluate_model.py --release-tag degraded --degrade # exit 1
$LASTEXITCODE
```

### 18.5 Retrain, promotion, déploiement et rollback

```powershell
./scripts/run_retrain.ps1 -MinFeedback 200   # skip si < 200 feedbacks
./scripts/run_retrain.ps1 -MinFeedback 1     # force le retrain avec le feedback créé en 18.3
Get-Content decisions_log.jsonl -Tail 1      # décision promoted / rejected + raison
./scripts/deploy_promoted.ps1 -Build         # uniquement si promoted
Invoke-RestMethod http://localhost:8000/info # version "promoted-..."

# Rollback vers le modèle par défaut
Remove-Item Env:MODEL_ARTIFACT
docker compose up -d --force-recreate model
Invoke-RestMethod http://localhost:8000/info
```

Les feedbacks utilisés sont marqués consommés : pour rejouer le scénario, il
faut en créer de nouveaux.

### 18.6 Monitoring et tracking

- Prometheus : http://localhost:9090/targets, cibles `model` et `backend` `UP`.
- Grafana : http://localhost:3001, panels `Vie`, `Vitesse`, `Comportement`
  alimentés après quelques `/score`.
- MLflow : http://localhost:5000, runs de `evaluate_model.py` et du retrain.

### 18.7 Dérive sur les données de production simulées

```powershell
python scripts/drift_analysis.py `
	--reference data/reference_set.csv `
	--current data/prod_3months.csv `
	--output reports/drift.json `
	--prometheus-output reports/drift.prom
```
