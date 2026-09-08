#!/bin/bash
set -euo pipefail
/opt/java/bin/java --version
/opt/signal/bin/signal-cli --version
/opt/java/bin/java -cp '/opt/signal/lib/*' /checks/LibsignalSmoke.java
perl -I /usr/src/app/3rdparty/lib/perl5 -MProtocol::DBus -MAI::FANN -e 'print "Perl modules load\n"'
# The base entrypoint normally creates fhem. This offline test bypasses that
# entrypoint to avoid its FHEM bootstrap downloads, so reproduce the user setup.
getent group fhem >/dev/null || groupadd --system fhem
id fhem >/dev/null 2>&1 || useradd --system --gid fhem --home-dir /opt/fhem --shell /bin/bash fhem
bash /docker/pre-start.sh
dbus-send --system --print-reply --reply-timeout=5000 \
    --dest=org.asamk.Signal /org/asamk/Signal \
    org.freedesktop.DBus.Introspectable.Introspect > /tmp/signal-introspection
grep -q 'org.asamk.Signal' /tmp/signal-introspection
echo "Offline Java/JNI, Perl and D-Bus smoke tests passed"
