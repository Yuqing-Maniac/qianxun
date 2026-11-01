n=0; while [ $n -lt 40 ]; do if pgrep -f "remotion render" >/dev/null; then n=0; else n=$((n+1)); fi; sleep 3; done
