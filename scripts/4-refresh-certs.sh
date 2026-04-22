#!/bin/bash
#
pushd $PWD

cd /home/admin/certs || exit

echo Check certs < 30 Tage
openssl x509 -in tribbleshare.follow-inconnu.ts.net.crt -noout -issuer -dates

if ! openssl x509 -checkend 2592000 -noout -in tribbleshare.follow-inconnu.ts.net.crt; then
  echo "⚠️ Zertifikat läuft in <30 Tagen ab - erneuere per Tailscale"
  tailscale cert --cert-file tribbleshare.follow-inconnu.ts.net.crt --key-file tribbleshare.follow-inconnu.ts.net.key tribbleshare.follow-inconnu.ts.net
  chmod go+r tribbleshare.follow-inconnu.ts.net.key
  ls -l /home/admin/certs
  openssl x509 -in tribbleshare.follow-inconnu.ts.net.crt -noout -issuer -dates
else
  echo "✅ Alles ok"
fi

popd
