#!/bin/bash
#
date
pushd $PWD

sudo restic -r sftp:ts_backup@box3:/F:/Backups/ts_backup backup /home/admin

popd
date
