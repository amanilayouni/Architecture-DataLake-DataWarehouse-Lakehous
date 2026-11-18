## Questions de recul

**1. Quel est le rôle du NameNode dans HDFS ?**

Le NameNode est le service qui gère l'espace de noms du système de fichiers : il sait quels fichiers et répertoires existent, comment chaque fichier est découpé en blocs et sur quels DataNodes ces blocs sont stockés. Il ne stocke pas les données elles-mêmes, seulement les métadonnées en mémoire et dans ses fichiers d'image (fsimage + edits). Sans NameNode, les données dans les DataNodes sont inexploitables : on ne sait plus à quel fichier appartiennent les blocs.

**2. Quelle différence existe entre un NameNode et un DataNode ?**

Le NameNode est le « cerveau » : un seul par cluster dans notre cas, il gère les métadonnées et répond aux demandes de localisation. Les DataNodes sont les « bras » : ils stockent les blocs de données sur disque, les servent en lecture et en écriture, et envoient régulièrement au NameNode un battement de cœur et la liste de leurs blocs. Sur notre environnement mono-nœud, les deux tournent sur la même machine.

**3. Pourquoi HDFS découpe-t-il les fichiers en blocs ?**

Parce que les fichiers peuvent dépasser la capacité d'un disque. Le découpage en blocs (128 Mo par défaut) permet de répartir un gros fichier sur plusieurs machines, de lire et écrire en parallèle, et de ne retransférer qu'un bloc en cas de problème plutôt que tout le fichier.

**4. Quel est l'intérêt de la réplication ?**

Chaque bloc est stocké plusieurs fois (3 par défaut) sur des DataNodes différents. Si un nœud tombe, les données restent accessibles depuis une autre copie et HDFS recrée les répliques manquantes. C'est ce qui rend le stockage fiable sur des machines ordinaires. Dans notre environnement, la réplication est à 1 car il n'y a qu'un DataNode : la tolérance de panne n'existe pas.

**5. Pourquoi organiser un Data Lake en plusieurs zones ?**

Pour séparer les responsabilités : Raw conserve les données reçues, Bronze la copie contrôlée, Silver les données nettoyées et typées, Gold les tables prêtes pour les indicateurs. Chaque zone a des utilisateurs et des règles différents (accès, immutabilité, format). Ça évite de mélanger des données brutes non fiables avec des données validées, et on peut toujours revenir à la source en cas de doute.

**6. Pourquoi conserver les données sources dans Raw ?**

Parce que les traitements peuvent contenir des erreurs ou évoluer. Si on ne garde que le résultat transformé, on ne peut pas vérifier d'où vient un chiffre ni rejouer une préparation corrigée. Raw sert de référence : les fichiers y sont déposés sans modification, avec leur provenance.

**7. Quel est le rôle d'un FlowFile dans NiFi ?**

Un FlowFile est l'unité qui circule dans le flux : un morceau de contenu (ici le fichier .dat) plus des attributs (nom, chemin, taille, date de prise en charge, identifiant unique). Les processeurs travaillent sur le FlowFile, et la provenance enregistre tout ce qui lui arrive. C'est ce qui permet de tracer un fichier de bout en bout.

**8. Quelle différence existe entre un Processor et une Connection ?**

Le Processor fait une action : lire un fichier local (GetFile), écrire dans HDFS (PutHDFS)... La Connection est le lien entre deux processeurs : c'est elle qui transporte le FlowFile et qui fait office de file d'attente quand le processeur en aval n'est pas encore prêt. Chaque connexion est associée à une relation (success, failure...).

**9. Pourquoi la provenance est-elle importante ?**

Elle répond aux questions « d'où vient ce fichier, que lui est-il arrivé, quand ». En cas d'anomalie dans les données, on peut retrouver le FlowFile à l'origine, l'heure de lecture, le chemin source et le dépôt effectué. C'est indispensable pour la confiance dans les indicateurs et pour le débogage.

**10. Comment distinguer un échec technique d'un rejet métier ?**

Un échec technique empêche le traitement de s'exécuter : service HDFS arrêté, permission refusée, chemin inexistant. Le fichier n'est pas lu ou pas déposé, c'est l'infrastructure qui est en cause. Un rejet métier, c'est un fichier qui a été lu mais qui ne respecte pas une règle de contenu : mauvaise extension, structure de colonnes non conforme, fichier vide. Il doit être mis de côté avec le motif plutôt que faire échouer tout le flux.

**11. Quels risques apparaissent si un flux est relancé sans contrôle des doublons ?**

On dépose le même fichier plusieurs fois : fichiers dupliqués dans HDFS, données comptées deux fois dans les agrégats, et avec Keep Source File = false on peut même traiter par erreur un fichier qui n'était pas prévu. Il faut une règle claire : stratégie de conflit « fail » dans PutHDFS, nommage qui inclut le lot, et vérification de la destination avant de relancer.

**12. Quelles limites présente un environnement mono-nœud ?**

Le NameNode et le DataNode sont sur la même machine : si elle tombe, tout est indisponible, et la réplication à 1 n'apporte aucune tolérance de panne. Les performances ne bénéficient pas du parallélisme entre machines. Ça suffit pour apprendre les commandes, mais ce n'est pas un cluster de production.

**13. Pourquoi une copie locale ne constitue-t-elle pas une preuve de dépôt HDFS ?**

Parce que copier un fichier d'un dossier local vers un autre ne passe par aucun mécanisme de HDFS : pas de bloc, pas de métadonnées NameNode, pas de permissions HDFS. On prouve seulement qu'un fichier a été copié, pas qu'il est stocké dans le Data Lake. La preuve d'un dépôt HDFS, c'est une sortie hdfs dfs -ls, -du ou -cat sur le chemin HDFS, ou l'événement de provenance du flux.

**14. Quelles informations doivent être conservées pour reproduire une ingestion ?**

La source exacte (chemin, nom, taille, empreinte), la destination HDFS, la date et l'heure, l'outil utilisé et sa configuration (commande hdfs ou paramètres des processeurs), l'utilisateur, et le résultat des vérifications. Avec le journal d'ingestion et les événements de provenance, on peut refaire ou contrôler la même opération plus tard.
