#!/bin/bash
#
date
pushd $PWD
sudo apt-get update
sudo apt-get upgrade
cd ~/tribbleshare.de/server || exit

sudo docker-compose pull
sudo docker-compose up -d

cd ~/tribbleshare.de/server/photoprism
sudo docker-compose pull
sudo docker-compose up -d

popd
date
