# Index des preuves UC-04

Sorties réelles du flux NiFi exécuté dans la VM (API REST + HDFS + journaux NiFi).

## configuration/

| Fichier | Contenu |
|---|---|
| `uc04_api_log.txt` | journal de la construction du flux via l'API REST : création des processeurs (avec leurs ids), erreurs de validation initiales et corrections, mise en `RUNNING`, compteurs de traitement |
| `08_flow_nifi_export.json.gz` | export de la définition complète du flux (fichier `flow.json.gz` de NiFi) : processeurs, propriétés, connexions |

## execution/

| Fichier | Contenu |
|---|---|
| `06_verification_nifi.txt` | `hdfs dfs -ls -h /retail-lake/raw/nifi/` (store.dat, 3,3 K), `hdfs dfs -ls -R /retail-lake` complet, `hdfs dfs -get` puis `sha256sum` du fichier déposé par NiFi comparé à l'original (identiques) |

## erreurs/

| Fichier | Contenu |
|---|---|
| `uc04_erreur_test.txt` | test A : GetFile pointé vers un dossier inexistant → refus de démarrage (STOPPED), puis chemin rétabli → RUNNING |
| `uc04_erreur2_test.txt` | test B : même nom de fichier déjà dans HDFS → bulletin « routing to failure », FlowFile transmis à LogAttribute, événements de provenance du doublon |
| `07_log_nifi_echec.txt` | ligne de `nifi-app.log` : PutHDFS pénalise le FlowFile `store.dat` et le route en `failure` (file already exists) |

## provenance/

| Fichier | Contenu |
|---|---|
| `provenance_run.json` | événements de provenance du dépôt réussi : RECEIVE (GetFile, avec `transitUri` et tous les attributs du FlowFile), SEND (PutHDFS vers HDFS), DROP après succès |
| `provenance_doublon.json` | événements du test de doublon : nouvelle lecture RECEIVE puis rejet routé en failure |

Remarque : les captures sont textuelles (API REST, HDFS CLI, journaux). L'interface NiFi (`https://localhost:8443/nifi` dans la VM) permet de visualiser les mêmes éléments sur le canvas.
