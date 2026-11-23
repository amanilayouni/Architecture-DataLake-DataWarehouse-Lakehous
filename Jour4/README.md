# Jour 4 — UC-08 : analyses et visualisation · UC-07 : architecture Azure

## UC-08 — Analyse des données et visualisation

Analyses réalisées dans la VM Ubuntu, environnement `j3` créé au Jour 3
(Python 3.10.18, PySpark 3.5.5, + pandas, matplotlib installés pour ce TP),
Spark en `local[2]`, sur les jeux Silver/Gold produits au Jour 3.

### Contenu

| Élément | Détail |
|---|---|
| Jeux | Silver `store_sales` (667 579 lignes), `item`, `store`, `date_dim` + Gold `ventes_mensuelles_magasin` (720 lignes) |
| KPI | K01 CA net, K03 transactions, K04 panier moyen, K05 quantités, K07 taux de remise, K08 marge |
| Statistiques | volumes, min/max/moyenne/médiane, distincts, période |
| Analyses | évolution mensuelle du CA, comparaison des 12 magasins (+ CA par catégorie) |
| Visualisations | 3 PNG dans `visualisations/` |

### Reproduction (VM)

```bash
export JAVA_HOME=/opt/java/jdk-17.0.21+9
export J3_OUT_DIR=/home/amani/j3_data     # jeux Silver/Gold du Jour 3
export J4_OUT_DIR=/home/amani/j4_data     # sorties CSV + PNG
PY=~/miniconda3/envs/j3/bin/python

# script (produit CSV dans outputs/ et PNG dans visualisations/)
$PY scripts/analyses.py

# ou le notebook (equivalent interactif)
~/miniconda3/envs/j3/bin/jupyter nbconvert --to notebook --execute \
    --inplace notebooks/analyses_kpi.ipynb
```

Résultats : `preuves/uc08/outputs/*.csv`, `visualisations/*.png`,
logs dans `preuves/uc08/`.

## UC-07 — Transposition sur Azure (parcours B : étude)

Pas d'abonnement Azure autorisé → **étude d'architecture**, aucune ressource
créée. Livrables :

- `architecture/schema_architecture.png` — réalisé (local) vs proposé (Azure)
- `architecture/organisation_adls.md` — zones bronze/silver/gold dans ADLS Gen2
- `architecture/matrice_permissions.pdf` — rôles, RBAC, ACL, moindre privilège
- `UC07_architecture_azure.pdf` — composants, HNS, ADF, Synapse,
  comparaison Azure/Open Source, limites

## Arborescence

```
Jour4/
├── UC08_analyses_visualisations.pdf
├── UC07_architecture_azure.pdf
├── livrables_jour4.pdf            option 2 : document unique
├── notebooks/analyses_kpi.ipynb   exécuté dans la VM
├── scripts/analyses.py
├── visualisations/                3 graphiques PNG
├── architecture/                  schema PNG, organisation ADLS, matrice
├── preuves/uc08/                  logs + CSV de résultats
├── preuves/uc07/                  index des elements produits/etudies
└── README.md
```

## Limites

- Données TPCx-BB synthétiques : constats à portée pédagogique.
- Spark `local[2]` mono-nœud ; pas de cluster.
- UC-07 : étude documentaire, distinguée des réalisations (Jours 2–4).
- Parties complémentaires (Power BI, Superset, Iceberg/Trino déployés) non
  réalisées — facultatives.
