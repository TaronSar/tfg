FROM ros:noetic-ros-base-focal

# Set the timezone non-interactively
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Basic installations
RUN apt-get update -yqq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -yqq --no-install-recommends \
    git nano curl wget g++ zsh software-properties-common

# ZSH
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.1.2/zsh-in-docker.sh)" -- \
    -t agnoster \
    -p git \
    -p https://github.com/zsh-users/zsh-autosuggestions \
    -p https://github.com/zsh-users/zsh-syntax-highlighting 

# Application dependencies - NVIDIA & Vulkan Drivers [rviz interface]
RUN export DEBIAN_FRONTEND=noninteractive && add-apt-repository ppa:graphics-drivers/ppa \
    && apt-get update -yqq && apt-get install -yqq nvidia-driver-470 nvidia-settings vulkan-utils

# QT5
RUN apt-get install -yqq qt5-default

# octomap
RUN apt-get install -yqq ros-${ROS_DISTRO}-octomap ros-${ROS_DISTRO}-octomap-msgs ros-${ROS_DISTRO}-octomap-server

# Clean up
RUN apt-get autoremove -yqq && apt-get autoclean -yqq

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /root

# Install application [rviz]
RUN apt-get install -yqq ros-noetic-rviz

# Install application [rviz interface]
COPY colibri_state_machine_msgs /root/interface_ws/src/colibri_state_machine_msgs
COPY colibri_uav_interface /root/interface_ws/src/colibri_uav_interface
COPY colibri_drone_flight_control_panel /root/interface_ws/src/colibri_drone_flight_control_panel
RUN cd /root/interface_ws \
    && source /opt/ros/$ROS_DISTRO/setup.bash \
    && catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
    && cd build && make install \
    && cd /root && rm -r /root/interface_ws

# Default command
CMD ["zsh"]