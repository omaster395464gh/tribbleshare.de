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
#  set unattended-upgrade options in /etc/apt/apt.conf.d/50unattended-upgrades
#   //
#   Unattended-Upgrade::Origins-Pattern {
#       // ...
#       // Tailscale Repo
#       "o=Tailscale,n=${distro_codename},l=Tailscale";
#       // ...

#   // (kernel images, kernel headers and kernel version locked tools).
#   Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
#   // Do automatic removal of newly unused dependencies after the upgrade
#   Unattended-Upgrade::Remove-New-Unused-Dependencies "true";
#   // Do automatic removal of unused packages after the upgrade
#   // (equivalent to apt-get autoremove)
#   Unattended-Upgrade::Remove-Unused-Dependencies "true";
#   // Automatically reboot *WITHOUT CONFIRMATION* if
#   //  the file /var/run/reboot-required is found after the upgrade
#   Unattended-Upgrade::Automatic-Reboot "true";
#   // Automatically reboot even if there are users currently logged in
#   // when Unattended-Upgrade::Automatic-Reboot is set to true
#   Unattended-Upgrade::Automatic-Reboot-WithUsers "true";
#   // If automatic reboot is enabled and needed, reboot at the specific
#   // time instead of immediately
#   //  Default: "now"
#   Unattended-Upgrade::Automatic-Reboot-Time "02:00";

#
# check:
#   time sudo /usr/local/sbin/3-auto-update-restart.sh && tail -n100 /var/log/auto-update-restart.log
#   systemctl list-timers auto-update-restart.timer
#
# run
#   sudo systemctl start auto-update-restart.service

LOGFILE="/var/log/auto-update-restart.log"
echo "===================" >> $LOGFILE
echo "===== $(date) =====" >> $LOGFILE
uptime >> $LOGFILE

# Updates einspielen
apt-get update >> $LOGFILE 2>&1
DEBIAN_FRONTEND=noninteractive \
  unattended-upgrade -v >> $LOGFILE 2>&1

# Dienste prüfen
NEEDRESTART_MODE=a \
  needrestart -r a >> $LOGFILE 2>&1

# Update images
su - admin -c "bash /home/admin/tribbleshare.de/scripts/1-do-upgrade.sh" >> $LOGFILE 2>&1

# Kernel-Reboot nötig?
if [ -f /var/run/reboot-required ]; then
  echo "Reboot required -> restarting..." >> $LOGFILE
  /sbin/reboot
else
  echo "No reboot needed." >> $LOGFILE
fi
