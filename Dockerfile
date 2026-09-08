# syntax=docker/dockerfile:1
ARG BASE_IMAGE=ghcr.io/fhem/fhem-docker:5-threaded-bookworm
FROM ${BASE_IMAGE}

ENV JAVA_HOME=/opt/java
ENV PATH=/opt/java/bin:${PATH}

LABEL org.opencontainers.image.authors="holoarts<holoarts@yahoo.com>"

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm

# Invalidate the APT layer weekly, including retries on subsequent days.
ARG APT_REFRESH_PERIOD=manual

# Upgrade all APT-managed packages within the configured Debian release.

RUN sudo dpkg --configure -a
RUN echo "APT refresh period: ${APT_REFRESH_PERIOD}" \
    && apt-get update \
    && apt-get -q -y -o Dpkg::Options::="--force-confold" upgrade \
    && apt-get -q -y install zip nano gcc tcpdump python-is-python3 libjson-perl libwww-perl libsoap-lite-perl libjson-xs-perl libany-uri-escape-perl libtext-iconv-perl libencode-perl libmp3-info-perl mp3wrap sox libsox-fmt-mp3 libreadonlyx-perl libfann-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN cpm install --show-build-log-on-failure --configure-timeout=360 --workers=$(nproc) --local-lib-contained /usr/src/app/3rdparty/  Readonly::XS List::MoreUtils Crypt::Rijndael Crypt::Random Crypt::Bcrypt Crypt::PBKDF2 LWP::UserAgent MIME::Base64 Time::HiRes Digest::MD5 base IO::File Net::SIP Protocol::DBus Math::Round AI::FANN


COPY scripts/install-signal.sh /tmp/install-signal.sh
COPY scripts/LibsignalSmoke.java /tmp/LibsignalSmoke.java
RUN --mount=type=bind,source=.build,target=/tmp/signal-input \
    bash /tmp/install-signal.sh
RUN chmod 1777 /tmp

COPY org.asamk.Signal.conf /etc/dbus-1/system.d/org.asamk.Signal.conf
COPY org.asamk.Signal.service /usr/share/dbus-1/system-services/org.asamk.Signal.service
COPY pre-start.sh /docker/
WORKDIR "/tmp"
