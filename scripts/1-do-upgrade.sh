#!/bin/bash
#
date
pushd $PWD
# sudo apt-get update
# sudo apt-get upgrade
cd ~/tribbleshare.de/server || exit

docker-compose pull
docker-compose up -d

cd ~/tribbleshare.de/server/photoprism
docker-compose pull
docker-compose up -d
docker system prune -f -a


popd
date
