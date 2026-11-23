# Organisation ADLS Gen2 proposée — Retail Intelligence Platform

Transposition des zones du data lake local (HDFS `/retail-lake`) vers un
conteneur ADLS Gen2. Aucune ressource Azure n'a été créée : organisation
proposée, non déployée.

## Cible proposée

```
conteneur : retail-intelligence
compte    : st<projet>datalake (HNS activé à la création, LRS)

retail-intelligence/
├── bronze/
│   └── tpcxbb/
│       ├── store_sales/    store_sales.dat (source inchangée)
│       ├── item/           item.dat
│       ├── date_dim/       date_dim.dat
│       └── store/          store.dat
├── silver/
│   ├── store_sales/        Parquet nettoyé (Jour 3)
│   ├── item/
│   ├── store/
│   └── date_dim/
├── gold/
│   └── ventes_mensuelles_magasin/    Parquet agrégé (Jour 3)
├── quality/
│   └── controles/          rapports de controles_qualite.py
├── logs/
│   └── traitements/        journaux d'exécution
└── documentation/
    ├── dictionnaire_kpi/
    └── conventions/
```

## Description des zones

| Zone | Fonction | Données stockées | Utilisateurs / traitements | Règles de nommage et traçabilité |
|---|---|---|---|---|
| bronze | Réception brute, copie fidèle des sources | `.dat` TPCx-BB tels quels | pipeline ADF (identité managée) | `bronze/tpcxbb/<table>/`, fichiers datés `yyyyMMdd`, jamais modifiés après dépôt |
| silver | Données nettoyées, typées, dédupliquées selon règles R1–R5 | Parquet par table | jobs Spark Data Engineering | `silver/<table>/part-*.parquet`, régénérable depuis bronze |
| gold | Agrégats répondant aux questions métier | Parquet par jeu de synthèse | jobs Spark, analystes | `gold/<jeu>/`, un jeu = une question métier documentée |
| quality | Preuves des contrôles qualité | rapports `.txt`/CSV | jobs qualité, revues | `controles_<date>.txt` |
| logs | Journaux des traitements | logs Spark, ADF | exploitation | un sous-dossier par traitement |
| documentation | Dictionnaires et conventions | dictionnaire KPI, schémas | toute l'équipe | versioning Git |

## Correspondance avec l'existant local

| ADLS Gen2 (proposé) | Local (réalisé) |
|---|---|
| `bronze/tpcxbb/` | HDFS `/retail-lake/raw/tpcxbb/` |
| `silver/` | `/home/amani/j3_data/silver/` |
| `gold/ventes_mensuelles_magasin/` | `/home/amani/j3_data/gold/ventes_mensuelles_magasin` |
| `quality/controles/` | `preuves/qualite/` (Jour 3) |

La transposition est directe : les fichiers Parquet produits localement peuvent
être copiés tels quels dans ADLS (`azcopy`, `az storage fs file upload` ou
pipeline ADF) ; les scripts PySpark ne changent que le préfixe des chemins
(`abfss://` au lieu de chemins locaux/HDFS).
