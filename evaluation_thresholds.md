# Seuils d'évaluation continue — Pyrenex scoring v2 (À COMPLÉTER)

> Doit être lisible par Sophie Léger (Lead Data) et le DPO. **Chaque seuil
> est justifié** par une raison chiffrée. Renommez en `evaluation_thresholds.md`.

Stratégie retenue (absolu / relatif / **hybride**) : _à choisir et justifier_.
Jeu de référence : `data/reference_set.csv` (sous-échantillon figé du holdout M1).

## Deux baselines, à ne pas confondre

| | Mesurée sur | Sert à |
|---|---|---|
| **Baseline communiquée** (`metrics_holdout`) | le holdout M1 complet | ce qu'on a annoncé au client |
| **Golden run** (`data/reference_baseline.json`) | **votre** jeu de référence, au gel | **arbitrer les releases** |

⚠️ Le garde-fou compare au **golden run**, jamais à la baseline communiquée :
les deux jeux n'ont ni la même taille ni la même composition, donc l'écart
entre eux mesure une **différence de population**, pas une dégradation du
modèle.

| Métrique | Golden run | Plancher absolu | Baisse max vs golden run | Justification |
|---|---:|---:|---:|---|
| F1 macro | 0.5951 | 0.56 | 0.04 | Le modèle doit rester au-dessus de 0.56, soit légèrement sous la baseline mais sans perte supérieure à 7%. |
| F1 default | 0.4211 | 0.36 | 0.05 | On garde une marge de sécurité sur la classe défaut, qui est la plus sensible métierlement. |
| ROC-AUC | 0.7247 | 0.70 | 0.04 | Le score doit rester acceptable pour la discrimination globale ; une baisse > 0.04 est trop forte. |
| Recall default | 0.6593 | 0.60 | 0.05 | Le recall défaut est prioritaire pour détecter les mauvais prêts ; on impose un plancher de 0.60. |

## Justification du "2σ"
Le jeu de référence contient 500 lignes. En bootstrap, la variabilité observée sur F1 et ROC-AUC est de l’ordre de 0.02–0.03.
Le seuil retenu est donc au-dessus du bruit de mesure, ce qui évite les faux positifs.

> **Comment dimensionner la colonne « baisse max »** : mesurez le bruit de
> votre jeu de référence (bootstrap, cf. mini-cours 08), et prenez **au moins
> 2 σ**. Une tolérance sous le bruit se déclenche toute seule. Reportez ici le
> σ mesuré — c'est ce qui rend le seuil défendable devant Sophie Léger.

| Métrique | σ bootstrap mesuré | 2 σ | Tolérance retenue |
|---|---:|---:|---:|
| F1 macro | 0.016 | 0.032 | 0.04 |
| ROC-AUC | 0.017 | 0.034 | 0.04 |
| Recall défaut | 0.020 | 0.040 | 0.05 |

## Procédure de mise à jour des seuils

- **Qui** : _…_
- **Quand** : _…_
- **Comment** : _… (garder `THRESHOLDS` dans le script ET ce fichier cohérents ;
  si le jeu de référence change, **regeler le golden run** — `--freeze-baseline`)_