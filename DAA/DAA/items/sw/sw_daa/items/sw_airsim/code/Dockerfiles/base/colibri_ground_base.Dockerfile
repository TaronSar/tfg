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

# Application dependencies [fleet manager / hpp]
RUN apt-get install -yqq --no-install-recommends libyaml-cpp-dev python-is-python3 python3-pip python3-tk\
    && echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> ~/.bashrc \
    && echo "source /opt/ros/$ROS_DISTRO/setup.zsh" >> ~/.zshrc

# Application dependencies - NVIDIA & Vulkan Drivers [rviz interface]
RUN export DEBIAN_FRONTEND=noninteractive && add-apt-repository ppa:graphics-drivers/ppa \
    && apt-get update -yqq && apt-get install -yqq nvidia-driver-470 nvidia-settings vulkan-utils

# Clean up
RUN apt-get autoremove -yqq && apt-get autoclean -yqq

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /root

# Install application [hpp]
COPY heuristic_path_planners/ /root/hpp_ws/src/heuristic_path_planners/
RUN export DEBIAN_FRONTEND=noninteractive \
    && rosdep fix-permissions && rosdep update \
    && rosdep install --from-paths -y /root/hpp_ws/src/heuristic_path_planners \
    && cd hpp_ws/ && source /opt/ros/$ROS_DISTRO/setup.bash \
    && catkin_make -j8 -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO -DBUILD_DOC=OFF \
    && cd build && make install \
    && cd /root && rm -r /root/hpp_ws

# Install application [fleet manager]
COPY colibri_fleet_manager/ /root/fleet_manager_ws/src/colibri_fleet_manager/
COPY colibri_state_machine_msgs/ /root/fleet_manager_ws/src/colibri_state_machine_msgs/
RUN export DEBIAN_FRONTEND=noninteractive \
    && rosdep update \
    && rosdep install --from-paths -y /root/fleet_manager_ws/src/colibri_fleet_manager \
    && pip3 install -r /root/fleet_manager_ws/src/colibri_fleet_manager/requirements.txt \
    && cd fleet_manager_ws/ && source /opt/ros/$ROS_DISTRO/setup.bash \
    && catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
    && echo "source /root/fleet_manager_ws/devel/setup.bash" >> ~/.bashrc \
    && echo "source /root/fleet_manager_ws/devel/setup.zsh" >> ~/.zshrc

# Install application [rviz]
RUN apt-get install -yqq ros-noetic-rviz ros-noetic-rqt-image-view

# Default command
CMD ["zsh"]