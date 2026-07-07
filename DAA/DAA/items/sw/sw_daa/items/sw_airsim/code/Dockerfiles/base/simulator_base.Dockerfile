FROM ubuntu:20.04

# Set the timezone non-interactively
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Basic installations
RUN apt-get update -yqq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -yqq --no-install-recommends \
    git nano curl wget g++ zsh software-properties-common

# Application dependencies - NVIDIA & Vulkan Drivers [UR simulator]
RUN export DEBIAN_FRONTEND=noninteractive && apt-get install -yqq libyaml-cpp-dev \
    && add-apt-repository ppa:graphics-drivers/ppa && apt-get update \
    && apt-get install -yqq nvidia-driver-470 nvidia-settings vulkan-utils

# Clean up
RUN apt-get autoremove -yqq && apt-get autoclean -yqq

# Create Default user and its password.
ARG USER=catec
ARG PASS=catec
RUN useradd --create-home --shell /bin/bash ${USER} \
            --password "$(openssl passwd -1 ${PASS})" && \
            usermod -aG sudo ${USER} && usermod -aG dialout ${USER}
USER ${USER}
RUN sed -i 's/#force_color_prompt=yes/force_color_prompt=yes/g' ~/.bashrc
WORKDIR /home/${USER}
SHELL ["/bin/bash", "-c"]

# Set environment variables
ENV NVIDIA_VISIBLE_DEVICES ${NVIDIA_VISIBLE_DEVICES:-all}
ENV NVIDIA_DRIVER_CAPABILITIES ${NVIDIA_DRIVER_CAPABILITIES:+$NVIDIA_DRIVER_CAPABILITIES,}graphics

# Default command 
CMD ["zsh"]