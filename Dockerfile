#FROM ghcr.io/fhem/fhem-docker:pr-266-threaded-bullseye
FROM fhem/fhem:pr-266-bullseye

MAINTAINER holoarts<holoarts@yahoo.com>

ENV DEBIAN_FRONTEND noninteractive
ENV TERM xterm

# Install dependencies
RUN apt-get update
#RUN apt-get -q -y install openjdk-21-jre-headless
RUN apt-get -q -y install zip
RUN apt-get clean && apt-get autoremove


WORKDIR "/opt"
#RUN wget https://download.oracle.com/java/21/latest/jdk-21_linux-x64_bin.deb
#RUN dpkg -i jdk-21_linux-x64_bin.deb
RUN wget https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.3%2B9/OpenJDK21U-jdk_x64_linux_hotspot_21.0.3_9.tar.gz
RUN tar zxf OpenJDK21U-jdk_x64_linux_hotspot_21.0.3_9.tar.gz
RUN mv jdk* java
RUN rm OpenJDK21U-jdk_x64_linux_hotspot_21.0.3_9.tar.gz

WORKDIR "/tmp"
RUN wget -qN https://github.com/AsamK/signal-cli/releases/download/v0.13.5/signal-cli-0.13.5.tar.gz -O signal-cli-0.13.5.tar.gz
RUN tar zxf signal-cli-0.13.5.tar.gz
RUN mv signal-cli-0.13.5  /opt/signal
RUN wget -qN https://github.com/exquo/signal-libs-build/releases/download/libsignal_v0.52.2/libsignal_jni.so-v0.52.2-x86_64-unknown-linux-gnu.tar.gz
RUN tar zxf libsignal_jni.so-v0.52.2-x86_64-unknown-linux-gnu.tar.gz
RUN zip -u /opt/signal/lib/libsignal-client-*.jar libsignal_jni.so

RUN rm -f signal-cli-0.13.5.tar.gz libsignal_jni.so
RUN cpan install Protocol::DBus
RUN cpan install Math::Round

COPY org.asamk.Signal.conf /etc/dbus-1/system.d/org.asamk.Signal.conf
COPY org.asamk.Signal.service /usr/share/dbus-1/system-services/org.asamk.Signal.service
COPY pre-start.sh /docker/

# End Dockerfile
