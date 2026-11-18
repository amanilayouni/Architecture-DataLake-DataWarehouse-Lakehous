# README — Jour 2 : reproduction des manipulations

Ce document explique comment reproduire les dépôts HDFS (UC-03) et le flux NiFi (UC-04) dans la VM. Toutes les preuves sont des exécutions réelles : Hadoop/HDFS et NiFi ont été installés et utilisés dans la VM Ubuntu, sur de vrais fichiers du kit TPCx-BB.

## 1. Environnement utilisé

| Élément | Valeur |
|---|---|
| Machine | VM VirtualBox `ubuntuu`, Ubuntu 16.04.7 LTS, 3 Go RAM, 1 vCPU |
| Java | OpenJDK Temurin 17.0.21 (Hadoop) et 21.0.13 (NiFi), dans `/opt/java/` |
| Hadoop | 3.5.0, `/opt/hadoop`, mode pseudo-distribué |
| NiFi | 2.12.0, `/opt/nifi`, HTTPS sur `localhost:8443` |
| Extensions NiFi | `nifi-hadoop-nar-2.12.0.nar` + `nifi-hadoop-libraries-nar-2.12.0.nar` (obligatoires pour PutHDFS) |
| Données | kit `retail_project` (TPCx-BB), copié dans `/home/amani/retail_project/` |

## 2. Installation (déjà faite — pour mémoire)

Le script `scripts/01_installation_environnement.sh` récapitule l'installation : extraction des JDK et de Hadoop dans `/opt`, configuration de `core-site.xml` (`fs.defaultFS = hdfs://localhost:9000`), `hdfs-site.xml` (réplication 1, dossiers `~/hadoop-data`), `hadoop-env.sh` (JAVA_HOME vers JDK 17, heap 512 Mo), puis installation de NiFi. Points de vigilance :

- créer `~/.ssh` et une clé (`ssh-keygen` + `authorized_keys`) avant le premier démarrage Hadoop ;
- les dossiers `~/hadoop-data` doivent appartenir à l'utilisateur (sinon NameNode/DataNode meurent au démarrage) ;
- `hdfs namenode -format` n'est à faire **qu'une fois**.

## 3. Démarrage / arrêt

```bash
export JAVA_HOME=/opt/java/jdk-17.0.21+9
export PATH=$PATH:/opt/hadoop/bin:/opt/hadoop/sbin:$JAVA_HOME/bin

start-dfs.sh                                  # demarre NameNode + DataNode + SecondaryNameNode
jps                                           # verifie les processus
hdfs dfsadmin -report                         # etat HDFS

JAVA_HOME=/opt/java/jdk-21.0.13+9 /opt/nifi/bin/nifi.sh start
JAVA_HOME=/opt/java/jdk-21.0.13+9 /opt/nifi/bin/nifi.sh status   # attendre "Status: UP"

# arret
JAVA_HOME=/opt/java/jdk-21.0.13+9 /opt/nifi/bin/nifi.sh stop
stop-dfs.sh
```

## 4. UC-03 — dépôt manuel

Le script `scripts/02_uc03_datalake_hdfs.sh` reproduit tout :

```bash
# arborescence (une fois)
for d in raw/tpcxbb/initial raw/tpcxbb/refresh raw/nifi bronze/tpcxbb silver gold quality logs; do
  hdfs dfs -mkdir -p /retail-lake/$d
done

# depot
hdfs dfs -put ~/retail_project/data/item/item.dat       /retail-lake/raw/tpcxbb/initial/
hdfs dfs -put ~/retail_project/data/date_dim/date_dim.dat /retail-lake/raw/tpcxbb/initial/

# verifications
hdfs dfs -ls -R /retail-lake
hdfs dfs -du -h /retail-lake
hdfs dfs -get /retail-lake/raw/tpcxbb/initial/item.dat /tmp/item_hdfs.dat
sha256sum /tmp/item_hdfs.dat ~/retail_project/data/item/item.dat   # doivent etre identiques
```

## 5. UC-04 — flux NiFi

1. Préparer les dossiers : `mkdir -p ~/data_nifi/input` et y copier `store.dat`.
2. Interface : `https://localhost:8443/nifi` dans la VM (identifiants générés par NiFi au premier démarrage, affichés dans `nifi-app.log` — ils ne sont pas dans ce dépôt).
3. Paramètres non sensibles du flux :

| Processeur | Paramètres |
|---|---|
| `GetFile_depot_local` | Input Directory : `/home/amani/data_nifi/input` ; Keep Source File : `false` |
| `PutHDFS_retail_lake` | Hadoop Configuration Resources : `/opt/hadoop/etc/hadoop/core-site.xml`, `hdfs-site.xml` ; Directory : `/retail-lake/raw/nifi` ; Conflict Resolution : `fail` |
| `LogAttribute_echecs` | défaut (journalise dans `nifi-app.log`) |

4. Le flux a été créé par `scripts/04_creer_flux_nifi.py` (API REST, token lu depuis `~/nifi_token.txt`, généré par login — non versionné). Les scripts `05_test_erreur_chemin.py` et `06_test_erreur_doublon.py` reproduisent les deux tests d'erreur.
5. Vérification : `hdfs dfs -ls -h /retail-lake/raw/nifi/` et Data Provenance dans l'interface.

## 6. Ce qui est une exécution réelle

- Dépôts manuels : `item.dat` et `date_dim.dat` réellement écrits dans HDFS (`raw/tpcxbb/initial/`).
- Dépôt NiFi : `store.dat` réellement lu par GetFile et écrit par PutHDFS dans `raw/nifi/`, avec événements de provenance.
- Tests d'erreur : chemin GetFile invalide (refus de démarrage) et doublon HDFS (routage failure → LogAttribute) réellement exécutés.
- Les schémas PNG sont des représentations de l'architecture, pas des exécutions.
- Les seuls éléments non reproductibles ici : les identifiants NiFi (secrets, restent dans la VM) et le token REST (temporaire).

## 7. Confidentialité

Ne pas versionner : les identifiants NiFi, `~/nifi_token.txt`, le kit de données `.dat` (1 Go), les fichiers `.gz` lourds d'export éventuels. Le `.gitignore` du dépôt couvre ces cas.
