# Jour 3 — UC-06 : Traitements Python/PySpark

Traitement des données TPCx-BB du data lake : exploration, nettoyage, production
des zones **Silver** et **Gold**, écriture Parquet et contrôles qualité.

## Prérequis

- VM Ubuntu (utilisée : VirtualBox, Ubuntu 16.04, 1 vCPU, ~3 Go RAM)
- HDFS actif (voir `Jour2/README_Jour2.pdf`) avec les fichiers `.dat` en zone Raw
- Miniconda dans `/home/amani/miniconda3`, environnement `j3`

Versions observées lors de l'exécution :

| Composant | Version |
|---|---|
| Python | 3.10.18 |
| PySpark | 3.5.5 |
| Java (JAVA_HOME) | OpenJDK 17.0.21 (`/opt/java/jdk-17.0.21+9`) |
| Mode Spark | `local[2]` |

## Données

Entrées lues depuis la zone Raw HDFS (`J3_RAW_MODE=hdfs`) :

| Table | Chemin HDFS |
|---|---|
| store_sales | `hdfs://localhost:9000/retail-lake/raw/tpcxbb/initial/store_sales.dat` |
| item | `hdfs://localhost:9000/retail-lake/raw/tpcxbb/initial/item.dat` |
| date_dim | `hdfs://localhost:9000/retail-lake/raw/tpcxbb/initial/date_dim.dat` |
| store | `hdfs://localhost:9000/retail-lake/raw/nifi/store.dat` |

Sans `J3_RAW_MODE`, les scripts lisent les copies locales `.dat`
(`J3_RAW_DIR`, défaut : dossier `data` du kit).

## Exécution (dans la VM)

```bash
export JAVA_HOME=/opt/java/jdk-17.0.21+9
export PATH=$JAVA_HOME/bin:$PATH
export J3_RAW_MODE=hdfs                 # lire la zone Raw HDFS
export J3_OUT_DIR=/home/amani/j3_data   # dossier parent des sorties
PY=~/miniconda3/envs/j3/bin/python

cd ~/j3
# 1. exploration (met a jour le notebook avec les sorties)
~/miniconda3/envs/j3/bin/jupyter nbconvert --to notebook --execute \
    --inplace notebooks/exploration.ipynb
# 2. nettoyage raw -> silver
$PY scripts/nettoyage.py
# 3. transformations : silver -> gold + comparaison Parquet/CSV/JSON
$PY scripts/transformations.py
# 4. controles qualite
$PY scripts/controles_qualite.py
```

## Sorties produites

| Sortie | Chemin (VM) | Contenu |
|---|---|---|
| Silver | `$J3_OUT_DIR/silver/<table>` | 4 jeux Parquet (667 579 ventes, 17 820 articles, 12 magasins, 109 573 jours) |
| Gold | `$J3_OUT_DIR/gold/ventes_mensuelles_magasin` | 720 lignes : CA net, quantités, marge par magasin x mois (2001-2005) |
| Parquet | `$J3_OUT_DIR/parquet/gold_csv`, `gold_json` | mêmes données en CSV/JSON pour comparaison |

Contrôles qualité : **21/21 OK**, dont Σ `ca_net` Gold = Σ `ss_net_paid` Silver
= 1 150 529 586,37.

## Arborescence du dossier

```
Jour3/
├── UC06_traitements_PySpark.pdf   dossier technique
├── livrables_jour3.pdf            option 2 : document unique
├── notebooks/exploration.ipynb    notebook executé dans la VM
├── scripts/                       common.py, nettoyage.py, transformations.py,
│                                  controles_qualite.py, tpcxbb_schema.py
├── data/inventaire_sources.txt
├── silver/  gold/  parquet/       jeux produits rapatriés de la VM
├── preuves/                       environnement, exploration, transformations,
│                                  silver_gold, parquet, qualite
└── README.md
```

## Limites connues

- Exécution en mode `local[2]` (un seul nœud), pas de cluster.
- Sorties Silver/Gold sur le disque local de la VM, pas redéposées dans HDFS.
- `marge_nette` négative : propriété des données synthétiques du kit.
- UC-05 (HBase/NoSQL) et parties avancées : non réalisés (facultatifs).
