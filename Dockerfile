# Native arm64 Ubuntu 18.04 environment, pinned to the inspected image digest.
FROM ubuntu@sha256:152dc042452c496007f07ca9127571cb9c29697f42acbfad72324b2bb2e43c98
ENV DEBIAN_FRONTEND=noninteractive GNU_MIRROR=https://mirrors.kernel.org/gnu
RUN apt-get update && apt-get install -y build-essential curl ca-certificates \
    xz-utils bzip2 patch texinfo automake libtool libtool-bin autoconf flex bison \
    libgmp-dev libmpfr-dev libmpc-dev libisl-dev libsdl2-dev python python3 \
    zip unzip git xvfb xdotool imagemagick && rm -rf /var/lib/apt/lists/*
ENV RBDEV_PREFIX=/opt/toolchain RBDEV_BUILD=/opt/toolchain-build RBDEV_DOWNLOAD=/opt/download
ENV PATH=/opt/toolchain/bin:$PATH
WORKDIR /opt
