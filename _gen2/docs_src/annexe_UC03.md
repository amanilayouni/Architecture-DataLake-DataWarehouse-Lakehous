# Index des preuves UC-03

Toutes les sorties ci-dessous sont des captures texte réelles des commandes exécutées dans la VM Ubuntu (aucune simulation).

## environnement/

| Fichier | Contenu |
|---|---|
| `01_environnement.txt` | OS de la VM, versions Java 17 et 21, `hadoop version` (3.5.0), `jps` (NameNode, DataNode, SecondaryNameNode, NiFi), `hdfs dfsadmin -report` complet (1 DataNode vivant, capacités, aucun bloc corrompu), `nifi.sh status` |

## data_lake/

| Fichier | Contenu |
|---|---|
| `02_arborescence.txt` | commandes `hdfs dfs -mkdir -p` de chaque zone, puis `hdfs dfs -ls /` et `hdfs dfs -ls -R /retail-lake` montrant l'arborescence créée |
| `03_fichiers_locaux.txt` | inventaire des 3 fichiers TPCx-BB copiés dans la VM : `ls -l` (taille réelle), `sha256sum` (empreinte), 2 premières lignes de chaque fichier |

## hdfs/

| Fichier | Contenu |
|---|---|
| `04_depot_hdfs.txt` | `hdfs dfs -put` de `item.dat` et `date_dim.dat` vers `/retail-lake/raw/tpcxbb/initial/`, puis `hdfs dfs -ls -h` (14,7 M et 6,5 M) |
| `05_verification.txt` | `hdfs dfs -du -h /retail-lake` (21,2 M dans raw), vérification des permissions, `hdfs dfs -cat \| head -3` (lecture contrôlée), `hdfs dfs -get` puis comparaison `sha256sum` (empreintes identiques) |

Remarques :

- Le warning `Unable to load native-hadoop library` présent dans les sorties est un avertissement standard sans impact sur les commandes.
- Le message `cat: Unable to write to output stream` après `head -3` est attendu : `head` ferme le tube avant la fin du fichier.
- Le schéma de l'arborescence (`j2_datalake_zones.png`) est intégré dans le document UC-03.
