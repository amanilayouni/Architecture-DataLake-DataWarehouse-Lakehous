export HADOOP_HOME=/opt/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:/opt/java/jdk-17.0.21+9/bin
cd ~/preuves_j2
{
echo "### java -version (JDK 17 Hadoop)"; /opt/java/jdk-17.0.21+9/bin/java -version
echo "### java -version (JDK 21 NiFi)"; /opt/java/jdk-21.0.13+9/bin/java -version
echo "### jps"; jps
echo "### nifi.sh status"; JAVA_HOME=/opt/java/jdk-21.0.13+9 /opt/nifi/bin/nifi.sh status
} >> 01_environnement.txt 2>&1
{
echo "### hdfs dfs -ls /retail-lake/raw/nifi/ (pas de doublon)"
hdfs dfs -ls -h /retail-lake/raw/nifi/
echo "### hdfs dfs -ls -R /retail-lake (arborescence finale)"
hdfs dfs -ls -R /retail-lake
echo "### integrite du fichier depose par NiFi"
hdfs dfs -get -f /retail-lake/raw/nifi/store.dat /tmp/store_nifi.dat
sha256sum /tmp/store_nifi.dat /home/amani/retail_project/data/store/store.dat
} > 06_verification_nifi.txt 2>&1
grep -iE "store.dat|flowfile" /opt/nifi/logs/nifi-app.log | grep -iE "penaliz|failure|attributes|filename" | tail -10 > 07_log_nifi_echec.txt
cp /opt/nifi/conf/flow.json.gz ./08_flow_nifi_export.json.gz
echo done
