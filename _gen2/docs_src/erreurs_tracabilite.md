## Erreurs, traçabilité et provenance

### Erreurs observées et traitées

| Erreur | Type | Détection | Traitement |
|---|---|---|---|
| Dossier d'entrée GetFile inexistant | configuration | validation NiFi au démarrage du processeur | processeur bloqué en STOPPED, chemin corrigé puis relancé |
| Fichier déjà présent dans HDFS | rejet métier (règle anti-écrasement) | `Conflict Resolution = fail` de PutHDFS | FlowFile routé en `failure` vers LogAttribute, bulletin émis, pas d'écrasement |
| PutHDFS inconnu de NiFi | environnement | HTTP 409 à la création du processeur | NAR Hadoop 2.12.0 ajoutés dans `extensions/` |
| NameNode/DataNode qui meurent au démarrage | environnement | `jps` + logs Hadoop | propriétaire de `~/hadoop-data` corrigé, reformatage |

### Chaîne de traçabilité d'un fichier

Pour `store.dat`, on peut suivre le fichier de bout en bout :

1. **Source** : `/home/amani/data_nifi/input/store.dat`, 3 386 o, empreinte `a936bc38...`.
2. **Lecture** : événement `RECEIVE` dans la provenance avec `transitUri`, attributs complets (propriétaire, dates, uuid).
3. **Écriture** : événement `SEND` de PutHDFS, puis `-rw-r--r-- 3.3K /retail-lake/raw/nifi/store.dat` côté `hdfs dfs -ls`.
4. **Fin** : `DROP` après succès, et vérification d'intégrité par `hdfs dfs -get` + `sha256sum` (empreinte identique).
5. **Rejet** : la seconde tentative produit le bulletin « file with same name already exists » et le passage par la connexion `failure` — visible aussi dans `nifi-app.log`.

### Ce qui resterait à ajouter en production

- Un nommage de fichier incluant le lot/la date pour éviter les collisions de noms.
- Une file dédiée aux rejets avec rejeu possible (ici LogAttribute journalise mais ne conserve pas le contenu).
- Une notification sur bulletin (les échecs sont visibles mais personne n'est alerté).
