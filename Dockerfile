FROM ghcr.io/fhem/fhem-docker:3-bullseye

MAINTAINER holoarts<holoarts@yahoo.com>

ENV DEBIAN_FRONTEND noninteractive
ENV TERM xterm

# Install dependencies
#RUN ping 192.168.5.1
#RUN ping 192.168.5.36
#RUN ping 8.8.8.8
#RUN cat /etc/resolv.conf
RUN apt-get update
RUN apt-get -q -y install openjdk-18-jre-headless
RUN apt-get -q -y install zip
RUN apt-get clean && apt-get autoremove


WORKDIR "/tmp"
RUN wget -qN https://github.com/AsamK/signal-cli/releases/download/v0.13.5/signal-cli-0.13.5.tar.gz -O signal-cli-0.13.5.tar.gz
RUN tar zxf signal-cli-0.13.5.tar.gz
RUN mv signal-cli-0.13.5  /opt/signal
RUN wget -qN https://github.com/exquo/signal-libs-build/releases/download/libsignal_v0.47.0/libsignal_jni.so-v0.47.0-x86_64-unknown-linux-gnu.tar.gz
RUN tar zxf libsignal_jni.so-v0.47.0-x86_64-unknown-linux-gnu.tar.gz
RUN zip -u /opt/signal/lib/libsignal-client-*.jar libsignal_jni.so

RUN rm -f signal-cli-0.13.5.tar.gz libsignal_jni.so
RUN cpan install Protocol::DBus

COPY org.asamk.Signal.conf /etc/dbus-1/system.d/org.asamk.Signal.conf
COPY org.asamk.Signal.service /usr/share/dbus-1/system-services/org.asamk.Signal.service
COPY pre-start.sh /docker/

#RUN /opt/signal/bin/signal-cli --config /var/lib/signal-cli

# End Dockerfile
