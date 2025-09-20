#!/bin/bash

# /usr/local/sbin/auto-update-restart.sh
#
# Installation
#   sudo cp 3-auto-update-restart.sh /usr/local/sbin/3-auto-update-restart.sh
#   sudo chmod +x /usr/local/sbin/3-auto-update-restart.sh
#   sudo cp auto-update-restart.service  /etc/systemd/system/auto-update-restart.service
#   sudo cp auto-update-restart.timer  /etc/systemd/system/auto-update-restart.timer
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now auto-update-restart.timer
#
# check:
#   time sudo /usr/local/sbin/3-auto-update-restart.sh && tail -n100 /var/log/auto-update-restart.log
#   systemctl list-timers auto-update-restart.timer
#
# run    
#   sudo systemctl start --now auto-update-restart.timer

LOGFILE="/var/log/auto-update-restart.log"
echo "===================" >> $LOGFILE
echo "===== $(date) =====" >> $LOGFILE
uptime >> $LOGFILE

# Updates einspielen
apt-get update >> $LOGFILE 2>&1
DEBIAN_FRONTEND=noninteractive \
  unattended-upgrade -v >> $LOGFILE 2>&1

# Alte Pakete entfernen
DEBIAN_FRONTEND=noninteractive \
  apt -y autoremove >> $LOGFILE 2>&1

# Dienste prüfen
NEEDRESTART_MODE=a \
  needrestart -r a >> $LOGFILE 2>&1

# Update images
su - admin -c "time bash /home/admin/tribbleshare.de/scripts/1-do-upgrade.sh" >> $LOGFILE 2>&1

# Kernel-Reboot nötig?
if [ -f /var/run/reboot-required ]; then
  echo "Reboot required -> restarting..." >> $LOGFILE
  /sbin/reboot
else
  echo "No reboot needed." >> $LOGFILE
fi
