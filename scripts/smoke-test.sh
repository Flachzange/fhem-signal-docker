#!/bin/bash
set -euo pipefail
/opt/java/bin/java --version
/opt/signal/bin/signal-cli --version
/opt/java/bin/java -cp '/opt/signal/lib/*' /checks/LibsignalSmoke.java
perl -I /usr/src/app/3rdparty/lib/perl5 -MProtocol::DBus -MAI::FANN -e 'print "Perl modules load\n"'
bash /docker/pre-start.sh
dbus-send --system --print-reply --reply-timeout=5000 \
    --dest=org.asamk.Signal /org/asamk/Signal \
    org.freedesktop.DBus.Introspectable.Introspect > /tmp/signal-introspection
grep -q 'org.asamk.Signal' /tmp/signal-introspection
echo "Offline Java/JNI, Perl and D-Bus smoke tests passed"
