#!/bin/bash -e
GERRIT_VERSION=2.12.2
deps=(
    java-1.7.0-openjdk
    wget
    git
    python-dulwich
)

yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
yum install -y "${deps[@]}"

wget \
    "https://www.gerritcodereview.com/download/gerrit-$GERRIT_VERSION.war" \
    --output-document gerrit.war

java -jar gerrit.war init --batch \
    --site-path /gerrit_testsite \
    --install-plugin commit-message-length-validator \
    --install-plugin download-commands \
    --install-plugin replication

for port in 8080 29418; do
    firewall-cmd --add-port $port/tcp
    firewall-cmd --add-port $port/tcp --permanent
done

## Download the latest bouncy castle libs, needed for ssh clone
pushd /gerrit_testsite/lib/
wget "https://www.bouncycastle.org/download/bcprov-jdk15on-154.jar"
wget "https://www.bouncycastle.org/download/bcpkix-jdk15on-154.jar"
../bin/gerrit.sh restart
popd
