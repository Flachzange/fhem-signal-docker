#!/bin/bash
set -euo pipefail
cd /tmp/signal-input
sha256sum --check SHA256SUMS
mkdir /tmp/signal-build
cd /tmp/signal-build
test "$(dpkg --print-architecture)" = amd64
mkdir -p /opt/java /opt/signal
tar -xzf /tmp/signal-input/java.tar.gz --strip-components=1 -C /opt/java
tar -xzf /tmp/signal-input/signal.tar.gz --strip-components=1 -C /opt/signal
mkdir native
tar -xzf /tmp/signal-input/libsignal.tar.gz -C native
mapfile -t libs < <(find native -type f -name libsignal_jni.so)
test "${#libs[@]}" -eq 1
mapfile -t jars < <(find /opt/signal/lib -maxdepth 1 -name 'libsignal-client-*.jar')
test "${#jars[@]}" -eq 1
# Replace unconditionally; zip -u can retain the old library based on timestamps.
cp "${libs[0]}" ./libsignal_jni.so
zip -j "${jars[0]}" libsignal_jni.so
install -m 0644 /tmp/signal-input/dependencies.json /opt/signal/dependencies.json
printf '%s\n' 'export JAVA_HOME=/opt/java' 'export PATH=/opt/java/bin:$PATH' \
    > /etc/profile.d/signal-java.sh
/opt/java/bin/java --version
/opt/signal/bin/signal-cli --version
/opt/java/bin/java -cp '/opt/signal/lib/*' /tmp/LibsignalSmoke.java
rm -rf /tmp/signal-build /tmp/LibsignalSmoke.java /tmp/install-signal.sh
