FROM ghcr.io/fhem/fhem-docker:5-threaded-bookworm

MAINTAINER holoarts<holoarts@yahoo.com>

ENV DEBIAN_FRONTEND noninteractive
ENV TERM xterm

# Install dependencies

RUN sudo dpkg --configure -a
RUN apt-get update
RUN apt-get -q -y install zip nano gcc tcpdump python-is-python3 libjson-perl libwww-perl libsoap-lite-perl libjson-xs-perl libany-uri-escape-perl libtext-iconv-perl libencode-perl libmp3-info-perl mp3wrap sox libsox-fmt-mp3 libreadonlyx-perl
RUN apt-get clean && apt-get autoremove

RUN cpm install --show-build-log-on-failure --configure-timeout=360 --workers=$(nproc) --local-lib-contained /usr/src/app/3rdparty/  Readonly::XS List::MoreUtils Crypt::Rijndael Crypt::Random Crypt::Bcrypt Crypt::PBKDF2 LWP::UserAgent MIME::Base64 Time::HiRes Digest::MD5 base IO::File Net::SIP Protocol::DBus Math::Round


WORKDIR "/opt"
RUN wget https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.2%2B10/OpenJDK25U-jdk_x64_linux_hotspot_25.0.2_10.tar.gz
RUN tar zxf OpenJDK25U-jdk_x64_linux_hotspot_25.0.2_10.tar.gz
RUN mv jdk* java
RUN rm OpenJDK25U-jdk_x64_linux_hotspot_25.0.2_10.tar.gz

WORKDIR "/tmp"
RUN wget -qN https://github.com/AsamK/signal-cli/releases/download/v0.14.1/signal-cli-0.14.1.tar.gz -O signal-cli-0.14.1.tar.gz
RUN tar zxf signal-cli-0.14.1.tar.gz
RUN mv signal-cli-0.14.1  /opt/signal
RUN wget -qN https://github.com/exquo/signal-libs-build/releases/download/libsignal_v0.90.0/libsignal_jni.so-v0.90.0-x86_64-unknown-linux-gnu.tar.gz
RUN tar zxf libsignal_jni.so-v0.90.0-x86_64-unknown-linux-gnu.tar.gz
RUN zip -u /opt/signal/lib/libsignal-client-*.jar libsignal_jni.so

RUN rm -f signal-cli-0.14.1.tar.gz libsignal_jni.so

COPY org.asamk.Signal.conf /etc/dbus-1/system.d/org.asamk.Signal.conf
COPY org.asamk.Signal.service /usr/share/dbus-1/system-services/org.asamk.Signal.service
COPY pre-start.sh /docker/

# End Dockerfile
