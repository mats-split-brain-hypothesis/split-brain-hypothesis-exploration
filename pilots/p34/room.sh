#!/usr/bin/env bash
# p34 desktop share: how many more sb- containers the desktop can take now under the shared cap (24, memory
# desktop-container-cap), after reserving what the other batches can still add: for each, its unlaunched jobs up to
# its own cap minus what it runs. 0 while less than MIN_FREE_MB is available.
#   bash pilots/p34/room.sh   -> a number
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain" CAP="${CAP:-24}" MIN_FREE_MB="${MIN_FREE_MB:-4000}"
n=$(docker ps -q --filter name=sb- | wc -l)
res=0
for b in p26:12 p30:12 p31:8 p32:8 p32x:7; do
    name=${b%%:*} bcap=${b#*:}
    jobs=$(awk 'NR > 1' "$PLAN/pilots/$name/jobs.tsv" 2>/dev/null | wc -l)
    [ -e "$SB/$name-queue.tsv.stop" ] && continue   # stopped at STOP_AT: launches nothing more
    unl=$(( jobs - $(cat "$SB/$name-queue.tsv" 2>/dev/null | wc -l) ))
    [ "$unl" -gt 0 ] || continue
    add=$(( bcap - $(docker ps -q --filter name=sb-$name- | wc -l) ))
    [ "$add" -gt "$unl" ] && add=$unl
    [ "$add" -gt 0 ] && res=$((res + add))
done
room=$(( CAP - n - res ))
[ "$(free -m | awk '/^Mem:/ {print $7}')" -ge "$MIN_FREE_MB" ] || room=0
echo $(( room > 0 ? room : 0 ))
