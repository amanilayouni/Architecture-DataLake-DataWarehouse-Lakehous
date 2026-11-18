#!/usr/bin/env bash
# UC-03 – Verification de l'environnement, creation du Data Lake, depot et controles.
# Toutes les sorties sont enregistrees dans ~/preuves_j2/ pour le dossier de preuves.
# Usage : bash uc03_etapes.sh <chemin_du_kit>   (ex. bash uc03_etapes.sh /home/$USER/retail_project)
set -u
KIT="${1:-$HOME/retail_project}"
PREUVES="$HOME/preuves_j2"
mkdir -p "$PREUVES"

echo "== 1. Environnement ==" | tee "$PREUVES/01_environnement.txt"
{
  echo "### date"; date
  echo "### lsb_release -a"; lsb_release -a 2>/dev/null
  echo "### uname -a"; uname -a
  echo "### java -version"; java -version 2>&1
  echo "### hadoop version"; hadoop version
  echo "### HADOOP_HOME=$HADOOP_HOME"
  echo "### jps"; jps
  echo "### hdfs dfsadmin -report"; hdfs dfsadmin -report
} >> "$PREUVES/01_environnement.txt" 2>&1

echo "== 2. Creation de l'arborescence ==" | tee "$PREUVES/02_arborescence.txt"
{
  for d in /retail-lake/raw/tpcxbb/initial /retail-lake/raw/tpcxbb/refresh \
           /retail-lake/raw/nifi /retail-lake/bronze/tpcxbb \
           /retail-lake/silver /retail-lake/gold /retail-lake/quality /retail-lake/logs; do
    echo "### hdfs dfs -mkdir -p $d"; hdfs dfs -mkdir -p "$d"
  done
  echo "### hdfs dfs -ls /"; hdfs dfs -ls /
  echo "### hdfs dfs -ls -R /retail-lake"; hdfs dfs -ls -R /retail-lake
} >> "$PREUVES/02_arborescence.txt" 2>&1

echo "== 3. Inventaire local des fichiers deposes ==" | tee "$PREUVES/03_fichiers_locaux.txt"
{
  for f in item date_dim store; do
    src="$KIT/data/$f/$f.dat"
    [ -f "$src" ] || src=$(find "$KIT" -name "$f.dat" | head -1)
    echo "### $src"
    ls -l "$src" 2>/dev/null
    sha256sum "$src" 2>/dev/null
    head -n 2 "$src" 2>/dev/null
    echo
  done
} >> "$PREUVES/03_fichiers_locaux.txt" 2>&1

echo "== 4. Depot manuel dans HDFS ==" | tee "$PREUVES/04_depot_hdfs.txt"
{
  ITEM=$(find "$KIT" -name "item.dat" -path "*/data/*" | head -1)
  DATE=$(find "$KIT" -name "date_dim.dat" -path "*/data/*" | head -1)
  echo "### hdfs dfs -put $ITEM /retail-lake/raw/tpcxbb/initial/"
  hdfs dfs -put "$ITEM" /retail-lake/raw/tpcxbb/initial/
  echo "### hdfs dfs -put $DATE /retail-lake/raw/tpcxbb/initial/"
  hdfs dfs -put "$DATE" /retail-lake/raw/tpcxbb/initial/
  echo "### hdfs dfs -ls -h /retail-lake/raw/tpcxbb/initial/"
  hdfs dfs -ls -h /retail-lake/raw/tpcxbb/initial/
} >> "$PREUVES/04_depot_hdfs.txt" 2>&1

echo "== 5. Verification du stockage ==" | tee "$PREUVES/05_verification.txt"
{
  echo "### hdfs dfs -du -h /retail-lake"; hdfs dfs -du -h /retail-lake
  echo "### hdfs dfs -ls -l /retail-lake/raw/tpcxbb/initial/ (permissions)"
  hdfs dfs -ls -l /retail-lake/raw/tpcxbb/initial/
  echo "### hdfs dfs -cat ... | head -3 (lecture controlee)"
  hdfs dfs -cat /retail-lake/raw/tpcxbb/initial/item.dat | head -3
  echo "### hdfs dfs -get + comparaison sha256"
  hdfs dfs -get /retail-lake/raw/tpcxbb/initial/item.dat /tmp/item_depuis_hdfs.dat
  sha256sum /tmp/item_depuis_hdfs.dat
  ITEM=$(find "$KIT" -name "item.dat" -path "*/data/*" | head -1)
  sha256sum "$ITEM"
} >> "$PREUVES/05_verification.txt" 2>&1

echo "Termine. Preuves dans $PREUVES"
