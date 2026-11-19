#!/usr/bin/env bash
# Installation Java 17 / 21, Hadoop 3.5.0 (pseudo-distribue) et NiFi 2.12.0
# Machine : VM VirtualBox Ubuntu 16.04, 3 Go RAM, 1 vCPU (heaps reduits)
set -e
cd ~/install

echo "== extraction des JDK =="
sudo mkdir -p /opt/java
sudo tar -xzf jdk17.tar.gz -C /opt/java
sudo tar -xzf jdk21.tar.gz -C /opt/java
sudo chown -R "$USER":"$USER" /opt/java
JDK17=$(ls -d /opt/java/jdk-17* | head -1)
JDK21=$(ls -d /opt/java/jdk-21* | head -1)
echo "JDK17=$JDK17"; echo "JDK21=$JDK21"
"$JDK17/bin/java" -version 2>&1 | head -1
"$JDK21/bin/java" -version 2>&1 | head -1

echo "== installation hadoop =="
tar -xzf hadoop-3.5.0.tar.gz
sudo mv hadoop-3.5.0 /opt/hadoop
sudo chown -R "$USER":"$USER" /opt/hadoop

H=/opt/hadoop
echo "export JAVA_HOME=$JDK17" >> $H/etc/hadoop/hadoop-env.sh
echo "export HADOOP_HEAPSIZE_MAX=512" >> $H/etc/hadoop/hadoop-env.sh

cat > $H/etc/hadoop/core-site.xml <<EOF
<configuration>
<property>
<name>fs.defaultFS</name>
<value>hdfs://localhost:9000</value>
</property>
</configuration>
EOF

cat > $H/etc/hadoop/hdfs-site.xml <<EOF
<configuration>
<property>
<name>dfs.replication</name>
<value>1</value>
</property>
<property>
<name>dfs.namenode.name.dir</name>
<value>file:///home/amani/hadoop-data/namenode</value>
</property>
<property>
<name>dfs.datanode.data.dir</name>
<value>file:///home/amani/hadoop-data/datanode</value>
</property>
</configuration>
EOF

mkdir -p ~/hadoop-data/namenode ~/hadoop-data/datanode

# variables d'environnement dans .bashrc (sans doublon)
grep -q HADOOP_HOME ~/.bashrc || cat >> ~/.bashrc <<EOF
export HADOOP_HOME=/opt/hadoop
export HADOOP_CONF_DIR=\$HADOOP_HOME/etc/hadoop
export JAVA_HOME_HADOOP=$JDK17
export JAVA_HOME_NIFI=$JDK21
export PATH=\$PATH:\$HADOOP_HOME/bin:\$HADOOP_HOME/sbin
EOF
export HADOOP_HOME=/opt/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin

# ssh localhost sans mot de passe (requis par start-dfs.sh)
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
grep -q id_ed25519 ~/.ssh/authorized_keys 2>/dev/null || cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys
ssh -o StrictHostKeyChecking=no localhost true

echo "== formatage du namenode (premiere installation) =="
$H/bin/hdfs namenode -format -force -nonInteractive > ~/install/format_namenode.log 2>&1
tail -5 ~/install/format_namenode.log

echo "== demarrage HDFS =="
$H/sbin/start-dfs.sh
sleep 8
$H/bin/hdfs version | head -2
jps

echo "== installation nifi =="
unzip -q nifi-2.12.0-bin.zip
sudo mv nifi-2.12.0 /opt/nifi
sudo chown -R "$USER":"$USER" /opt/nifi
# heap reduit pour 3 Go de RAM
sed -i 's/^java.arg.2=.*/java.arg.2=-Xms256m/; s/^java.arg.3=.*/java.arg.3=-Xmx768m/' /opt/nifi/conf/bootstrap.conf
grep -E 'java.arg.[23]' /opt/nifi/conf/bootstrap.conf

echo "INSTALL TERMINEE"
