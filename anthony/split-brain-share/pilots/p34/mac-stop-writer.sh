#!/opt/homebrew/bin/bash
# p34 handoff (p34-desk-go.sh), on the Mac: once the Mac queue has launched every job still marked mac in jobs.tsv,
# write $QT.stop (the ids moved to the desktop) so the Mac finisher stops waiting for jobs it will never launch.
SB="$HOME/split-brain-run" JOBS="$HOME/split-brain/pilots/p34/jobs.tsv" QT="$HOME/split-brain-run/p34-queue.tsv"
ids=$(awk -F'\t' 'NR > 1 && $8 == "mac" {print $1}' "$JOBS")
while true; do
    left=0; for id in $ids; do grep -qs "^$id	" "$QT" || left=$((left + 1)); done
    [ "$left" = 0 ] && break
    sleep 60
done
awk -F'\t' 'NR > 1 && $8 == "desktop" {print $1}' "$JOBS" > "$QT.stop"
echo "$(date '+%F %T') all Mac jobs launched: $QT.stop written ($(wc -l < "$QT.stop" | tr -d ' ') ids on the desktop)"
