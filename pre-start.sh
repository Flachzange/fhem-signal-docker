#!/bin/bash
# Original integration: Holoarts, GPL.
# Start the components already installed in the image; no runtime downloads.
set -euo pipefail
export JAVA_HOME=/opt/java
export PATH="$JAVA_HOME/bin:$PATH"
service dbus start
mkdir -p /var/lib/signal-cli
chown fhem:fhem /var/lib/signal-cli
touch /var/log/signal.log /var/log/signal.err
sudo -u fhem env JAVA_HOME="$JAVA_HOME" PATH="$PATH" \
    /opt/signal/bin/signal-cli --config /var/lib/signal-cli daemon --system \
    >> /var/log/signal.log 2>> /var/log/signal.err &
signal_pid=$!

for ((attempt=0; attempt<60; attempt++)); do
    if ! kill -0 "$signal_pid" 2>/dev/null; then
        echo "signal-cli exited during startup" >&2
        tail -n 50 /var/log/signal.err >&2
        exit 1
    fi
    if dbus-send --system --print-reply --reply-timeout=1000 \
        --dest=org.freedesktop.DBus /org/freedesktop/DBus \
        org.freedesktop.DBus.NameHasOwner string:org.asamk.Signal \
        2>/dev/null | grep -q 'boolean true'; then
        echo "signal-cli is ready on the system D-Bus"
        exit 0
    fi
    sleep 1
done
echo "signal-cli did not become ready within 60 seconds" >&2
tail -n 50 /var/log/signal.err >&2
kill "$signal_pid" 2>/dev/null || true
exit 1
