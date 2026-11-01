#!/bin/sh
# single-instance: start, second --toggle, kill -9, stale socket, restart. Run under xvfb-run.
APP=$(cd "$(dirname "$0")/../.." && pwd)/app/qianxun.py
T=$(mktemp -d); export HOME=$T XDG_CONFIG_HOME=$T/c XDG_CACHE_HOME=$T/k
mkdir -p "$T/c/qianxun" "$T/r"; touch "$T/r/hello.txt"
printf '{"roots":["%s/r"],"index_removable":false}' "$T" > "$T/c/qianxun/config.json"
python3 "$APP" & P1=$!
sleep 3
kill -0 $P1 || { echo "FAIL first instance died"; exit 1; }
timeout 10 python3 "$APP" --toggle; echo "second rc=$? (expect 0, immediate)"
timeout 10 python3 "$APP" --hidden; echo "third rc=$?"
kill -0 $P1 && echo "first still alive"
kill -9 $P1; sleep 0.5
ls -la /tmp/qianxun-$(id -u) 2>/dev/null && echo "stale socket present"
python3 "$APP" & P2=$!
sleep 3
kill -0 $P2 && echo "restart after kill -9 OK" || echo "FAIL restart"
timeout 10 python3 "$APP" --toggle; echo "toggle to restarted rc=$?"
kill -TERM $P2; sleep 2; kill -0 $P2 2>/dev/null && { echo "FAIL: SIGTERM ignored"; kill -9 $P2; } || echo "SIGTERM exits"
rm -rf "$T"
