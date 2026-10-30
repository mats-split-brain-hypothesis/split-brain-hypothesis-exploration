#!/bin/bash
# As root: shut the network down to the allowlist, remove the obvious container marker, then run the command as
# anthony (who has no sudo, so cannot undo the firewall).
set -euo pipefail
/usr/local/sbin/init-firewall.sh >&2
rm -f /.dockerenv
export HOME=/home/anthony USER=anthony
cd /home/anthony/j-lens-mean
exec gosu anthony "$@"
