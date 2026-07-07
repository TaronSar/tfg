FROM ubuntu:22.04

# Evitar preguntas interactivas durante la instalación
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias requeridas por PetaLinux 2023.1 (Completas y parcheadas)
RUN apt-get update && apt-get install -y \
    build-essential sudo locales bash-completion \
    gawk wget git diffstat unzip texinfo gcc-multilib \
    chrpath socat cpio python3 python3-pip python3-pexpect \
    xz-utils debianutils iputils-ping python3-git python3-jinja2 \
    libegl1-mesa libsdl1.2-dev pylint xterm python3-subunit \
    mesa-common-dev zstd liblz4-tool xxd file tar tzdata rsync \
    bc net-tools autoconf libtool libncurses5-dev libncursesw5-dev lsb-release \
    libtinfo5 screen tmux \
    && rm -rf /var/lib/apt/lists/*

# Cambiar /bin/sh para que apunte a bash (requisito estricto de PetaLinux)
RUN echo "dash dash/sh boolean false" | debconf-set-selections && dpkg-reconfigure -f noninteractive dash

# Configurar idioma (Requisito estricto de Yocto)
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Crear un usuario con el mismo UID/GID que tu host (asumiendo 1000:1000)
RUN groupadd -g 1000 ijm1 && \
    useradd -u 1000 -g 1000 -m -s /bin/bash ijm1 && \
    echo "ijm1 ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER ijm1
WORKDIR /home/ijm1