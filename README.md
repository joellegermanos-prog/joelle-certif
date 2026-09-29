# M5-B1 + M5-B2 — Pyrenex Prod (architecture, CI/CD, monitoring, éval continue)

> **Repo template GitHub.** Un·e des 2 du binôme clique **« Use this
> template »** → `M5-B1-pyrenex-prod-<binome>`, puis ajoute l'autre comme
> collaborateur. Vous partez du **scoring v2** (modèle M1 fourni) et vous le
> mettez en **production complète** : 3 services orchestrés, CI/CD, monitoring
> Grafana, runbook, puis (B2) évaluation continue + tracking MLflow.

---

## 🧭 Votre brief en un coup d'œil

**Ce README est votre document de pilotage unique** — tout ce qu'il faut faire,
dans l'ordre, avec le bon appui. Les autres supports ont chacun un rôle précis :

| Support | Rôle |
|---|---|
| **Simplonline** | Le contrat : contexte client, livrables, critères de performance |
| **Ce README** | Le pilotage : quoi faire, quand, avec quel mini-cours |
| [`ressources/`](./ressources/) | Les 8 mini-cours d'appui (index dans [`ressources/README.md`](./ressources/README.md)) |
| **Discord `fil-M5`** | Annonces + questions |

### M5-B1 — les 2 jours sync (binôme)

> La numérotation des tâches est celle de l'énoncé Simplonline (1 → 12).
> La tâche 4, c'est le déjeuner : elle compte aussi.

| Quand | Tâche | Durée | Appui |
|---|---|---|---|
| Mardi 10h35 | 1. Tirage binôme + appropriation de la reprise M1 (modèle + API fournis) | 45 min | — |
| Mardi 11h20 | 2. Architecture 3 services (`model` / `backend` / `frontend`) — 1ʳᵉ partie | 1h10 | [`01_Docker_compose`](./ressources/01_Docker_compose_multiservices_essentiel.md) |
| Mardi 12h30 | 4. 🍽️ Déjeuner | 1h | — |
| Mardi 13h30 | 2. Architecture 3 services — fin | 20 min | [`01_Docker_compose`](./ressources/01_Docker_compose_multiservices_essentiel.md) |
| Mardi 13h50 | 3. Vérification `docker compose up` | 15 min | [`01_Docker_compose`](./ressources/01_Docker_compose_multiservices_essentiel.md) |
| Mardi 14h05 | 5. Pipeline CI/CD GitHub Actions + *quality gate* (pause 15 min incluse) | 2h30 | [`03_GitHub_Actions`](./ressources/03_GitHub_Actions_CI_CD_essentiel.md) — appui [`06_Pair_coding`](./ressources/06_Pair_coding_sync_long_essentiel.md) |
| Mardi 16h45 | 6. Mur réflexif intermédiaire | 15 min | — |
| Mercredi 9h15 | 7. Endpoint `/metrics` + métriques métier | 30 min | [`02_FastAPI_metrics_Prometheus`](./ressources/02_FastAPI_metrics_Prometheus_essentiel.md) |
| Mercredi 9h45 | 8. Prometheus + Grafana dans le compose | 30 min | [`02_FastAPI_metrics_Prometheus`](./ressources/02_FastAPI_metrics_Prometheus_essentiel.md) |
| Mercredi 10h15 | 9. Dashboard Grafana custom (vie / vitesse / comportement) | 45 min | [`04_Grafana_dashboard`](./ressources/04_Grafana_dashboard_custom_essentiel.md) |
| Mercredi 11h00 | 10. Runbook d'astreinte (4 procédures) | 30 min | [`05_Runbook_astreinte`](./ressources/05_Runbook_astreinte_essentiel.md) |
| Mercredi 11h30 | 11. **Tour de table binômes** (démo compose + dashboard) | 1h | — |
| Mercredi 12h30 | 12. Mur réflexif final M5-B1 + lancement M5-B2 | 30 min | — |

> ⏱️ **Le jalon qui compte** : vos 3 services doivent démarrer **avant
> d'attaquer la CI**. Si la tâche 3 n'est pas verte à 14h05, appelez —
> la tâche 5 est la plus longue des deux jours, elle ne se rattrape pas.

### M5-B2 — l'async individuel (jeudi + vendredi matin, 6 h)

Vous repartez **chacun·e** du dépôt du binôme. Pas de nouveau dépôt.

| Quand | Étape | Durée | Appui |
|---|---|---|---|
| Jeudi | 1. **Préparation du jeu de référence** — récupérer le holdout M1, en tirer **votre** `data/reference_set.csv` (~500 lignes), puis geler le golden run (`--freeze-baseline`) | 30 min | [`data/README.md`](./data/README.md) + [`08_Evaluation_continue_seuils`](./ressources/08_Evaluation_continue_seuils_essentiel.md) |
| Jeudi | 2. `scripts/evaluate_model.py` + tracking **MLflow** (4 métriques, code retour 0 / non-zéro) | 1h30 | [`07_MLflow_tracking`](./ressources/07_MLflow_tracking_essentiel.md) + [`08`](./ressources/08_Evaluation_continue_seuils_essentiel.md) |
| Jeudi | 3. Définition et **justification** des seuils (`evaluation_thresholds.md`) | 1h | [`08_Evaluation_continue_seuils`](./ressources/08_Evaluation_continue_seuils_essentiel.md) |
| Vendredi | 4. Étape `evaluate-model` bloquante dans le workflow GitHub Actions | 1h | [`03_GitHub_Actions`](./ressources/03_GitHub_Actions_CI_CD_essentiel.md) |
| Vendredi | 5. Tests pytest pour l'évaluation | 45 min | [`03_GitHub_Actions`](./ressources/03_GitHub_Actions_CI_CD_essentiel.md) |
| Vendredi | 6. ⭐ Alerte Discord webhook (**bonus**) | 30 min | — |
| Vendredi | 7. Doc + merge | 45 min | — |

> ⚠️ **Le piège central de B2** : votre jeu de référence n'existe pas encore,
> et le fichier `data/reference_set_TEMPLATE.csv` du repo n'en est **pas** un
> (20 lignes = un exemple de format). C'est vous qui le construisez à partir du
> holdout M1, et sa composition est une **décision à argumenter**.
> Mode d'emploi : [`data/README.md`](./data/README.md).

### ✅ Checklist livrables

**M5-B1 — avant mercredi 12h30**

- [ ] `docker compose up --build` démarre les **3 services** de façon **reproductible**, healthchecks verts
- [ ] `/metrics` exposé côté `model` **et** `backend`
- [ ] Dashboard Grafana provisionné **automatiquement** (3 panels : vie / vitesse / comportement)
- [ ] Workflow CI **vert**, image poussée sur GHCR, tag `v1.0.0-prod`
- [ ] Le **contract test** du modèle bloque la release s'il est rouge
      *(il vérifie le **contrat technique** de l'API — pas la performance du
      modèle : ça, c'est l'évaluation continue de B2)*
- [ ] `runbook.md` — 4 procédures (Service KO / Latence / Métrique modèle / Rollback)
- [ ] `README.md` — schéma Mermaid de l'archi + démarrage en 3 commandes
- [ ] Commits binôme : `Co-authored-by:` ou auteurs nominatifs

**M5-B2 — avant vendredi 17h**

- [ ] `data/reference_set.csv` (~500 lignes) **construit par vous** depuis le holdout M1, figé, versionné
- [ ] `data/reference_baseline.json` — le golden run, gelé sur **ce** jeu
- [ ] `scripts/evaluate_model.py` — 4 métriques, ≥ 2 runs MLflow comparables
- [ ] `evaluation_thresholds.md` — 4 métriques × golden run / plancher absolu / baisse max / **justification**, tolérance relative ≥ 2 σ (bootstrap)
- [ ] Étape `evaluate-model` dans la CI : `--degrade` fait **échouer** la release
  *(`mlruns/` est gitignoré : les métriques et violations sont publiées dans le résumé du run GitHub Actions)*

---

## � Évaluation continue (golden run + seuils + MLflow)

La validation continue du modèle ne compare plus le modèle courant à un holdout aléatoire différent. Le principe est stable et reproductible :

- on construit un jeu de référence figé à partir du holdout M1,
- on calcule un `golden run` qui sert de référence autorisée,
- chaque nouveau run est évalué sur le même jeu de référence,
- la release est bloquée si une métrique dégrade trop ou si le seuil absolu est franchi.

### 1) Jeu de référence et golden run

- `data/reference_set.csv` : jeu de référence figé (~500 lignes), versionné dans le dépôt.
- `data/reference_baseline.json` : snapshot du golden run (métriques et paramètres de référence).

Le script de gel est déclenché ainsi :

```bash
python scripts/evaluate_model.py --freeze-baseline
```

Le golden run est le point d'ancrage de la release gate. Il ne doit pas être recalculé à la légère : il représente la performance acceptable de référence.

### 2) Script d'évaluation

Le cœur du gate est dans `scripts/evaluate_model.py`.

Il calcule au minimum :

- précision / accuracy,
- roc_auc ou métrique métier ciblée,
- f1-score ou score de décision,
- métriques de stabilité / qualité du score (selon la définition de votre projet).

Le script vérifie ensuite :

- le seuil absolu de chaque métrique,
- la baisse relative par rapport au golden run,
- les cas de régression trop importantes.

En cas de défaillance, le script renvoie un code de sortie non nul et la CI est bloquée.

### 3) MLflow tracking

Chaque run est injecté dans MLflow avec :

- paramètres d'inférence / versionnement,
- métriques de validation,
- labels de run pour comparaison,
- artefacts de traçabilité si nécessaire.

Pour visualiser les runs locaux :

```bash
mlflow ui
```

Puis ouvrir : http://localhost:5000

L'UI permet de comparer les performances entre runs, d'identifier la régression et de justifier la décision de blocage ou de validation.

### 4) CI / release gate

Le workflow GitHub Actions contient un job bloquant :

```yaml
evaluate-model:
  needs: evaluation-tests
  runs-on: ubuntu-latest
```

Le job exécute :

```bash
python scripts/evaluate_model.py --release-tag ${{ github.ref_name }}
```

Si l'évaluation est rouge, la release est stoppée avant publication de l'image Docker.

Le mode `--degrade` est réservé aux tests de preuve rouge :

```bash
python scripts/evaluate_model.py --release-tag ${{ github.ref_name }} --degrade
```

Il permet de simuler volontairement une régression afin de valider l'alerte sans modifier la logique de production.

### 5) Alerte Discord

Le workflow peut aussi envoyer une alerte Discord en cas d'échec de la gate evaluation.

Le secret GitHub attendu est :

```text
DISCORD_WEBHOOK_URL
```

avec une valeur de type :

```text
https://discord.com/api/webhooks/....
```

Le notifier ne se déclenche que si le job `evaluate-model` échoue. Il ne faut pas utiliser un lien de salon `discord.com/channels/...` ; il faut bien un webhook Discord.

![alt text](image-1.png)


### 6) Règle de décision

Une release est validée si et seulement si :

- les tests unitaires passent,
- le golden run est bien utilisé comme référence,
- les métriques restent au-dessus des seuils définis,
- le run MLflow est tracé et comparable,
- la CI n'est pas bloquée par une régression.

Cette logique garantit une politique de validation explicite et reproductible, sans dépendre du hasard d'un jeu différent à chaque run.

---

## �🚀 Démarrage (le service `model` tourne déjà)

```bash
# 1. Environnement de tests local (optionnel mais conseillé)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. Vérifier que la base fournie passe les tests
pytest -v services/model/tests

# 3. Lancer ce qui est déjà câblé (model + prometheus + grafana)
docker compose up --build
```

> 🧰 **Avec `uv`** : `uv venv && source .venv/bin/activate` puis
> **`uv pip install -r requirements-dev.txt`**.
> ⚠️ Un venv créé par `uv venv` **n'embarque pas `pip`** : si vous voyez
> `No module named pip`, c'est ça — utilisez `uv pip install`, pas `pip install`.

> ⚠️ **Ports hôte** : frontend **8088** (pas 8080), Grafana **3001** (pas 3000)
> — pour éviter les conflits courants. Model 8000, backend 8001, Prometheus 9090.

### Déclenchement du retrain

Les feedbacks sont conservés dans le volume Docker `feedback_data`. Le
retrainer partage ce volume avec le backend et applique le seuil de 200
feedbacks non consommés :

Initialiser uniquement le schéma SQLite, sans générer de faux feedbacks :

```powershell
python scripts/init_feedback_db.py
```

```powershell
./scripts/run_retrain.ps1
./scripts/run_retrain.ps1 -MinFeedback 1
```

Sous Linux ou via cron :

```bash
./scripts/run_retrain.sh 200
```

Le workflow [retrain.yml](.github/workflows/retrain.yml) ajoute un lancement
planifié toutes les six heures et un lancement manuel. Il s'exécute sur le
runner auto-hébergé Windows installé sur l'hôte de déploiement (labels
`self-hosted`, `windows`, `x64`, `cisia-prod`) : aucun port entrant ni secret
SSH n'est nécessaire. Configurez la variable de dépôt `DEPLOY_PATH` vers le
répertoire Compose de production, et exécutez le service du runner avec un
compte Windows qui a accès au moteur Docker.

Le job force le projet Compose `certification` pour réutiliser le volume
`certification_feedback_data`, partagé avec le backend, puis récupère l'image
`retrainer` épinglée au commit. Le script journalise l'exécution dans MLflow
et écrit `reports/retrain-result.json`; `SLACK_WEBHOOK_URL` reste facultatif
et ne sert qu'aux notifications. Si le candidat est promu, le workflow met à
jour `MODEL_ARTIFACT` dans le `.env` local ignoré par Git et recrée `model`
pour charger l'artefact promu; cette sélection reste active lors des prochains
`docker compose up`.

Après une décision `promoted`, le modèle promu peut être déployé localement :

```powershell
./scripts/deploy_promoted.ps1 -Build
```

Le script vérifie les deux artefacts promus, configure `MODEL_ARTIFACT`,
recrée `model`, `backend` et `frontend`, puis affiche leur état Docker. Sans
artefact promu, aucun déploiement n'est lancé.

Au départ, seuls `model`, `prometheus` et `grafana` démarrent : à vous
d'ajouter `backend` + `frontend` et de compléter le reste (cf. TODO).

---

## 📁 Structure

```
services/
  model/        # FOURNI — API scoring M1-B2 + /metrics (ne pas réécrire)
  backend/      # À COMPLÉTER — orchestrateur (tâche 2)
  frontend/     # À COMPLÉTER — formulaire nginx (tâche 2)
prometheus/     # FOURNI — scrape config
grafana/provisioning/
  datasources/  # FOURNI — datasource Prometheus
  dashboards/   # provider fourni ; le dashboard JSON = à vous (tâche 9)
.github/workflows/ci.yml   # squelette (job test fourni) — tâche 5
runbook.md                 # template 4 sections — tâche 10
data/README.md                       # B2 — d'où vient votre jeu de référence
data/reference_set_TEMPLATE.csv      # B2 — exemple de FORMAT (20 lignes), pas un jeu
scripts/evaluate_model_TEMPLATE.py   # B2 — MLflow pré-câblé
evaluation_thresholds_TEMPLATE.md    # B2 — seuils à justifier
ressources/                # 📚 mini-cours d'appui (lecture juste-à-temps)
```

> Le service `model` (déjà fourni) est votre **exemple de référence** : il
> expose déjà `/metrics` — répliquez ce pattern sur le `backend`.

---

## 📚 Ressources

Voir [`./ressources/`](./ressources/) — 8 mini-cours + `liens_officiels.md`.
Lecture **juste-à-temps** : ouvrez le mini-cours de la tâche en cours.

---

## 🆘 Bloqué·e·s ?

1. Relisez le mini-cours de la tâche en cours (`ressources/`).
2. Le service `model` est votre exemple qui marche : copiez ses patterns.
3. 30 min sur un bloquant → Discord `fil-M5`.