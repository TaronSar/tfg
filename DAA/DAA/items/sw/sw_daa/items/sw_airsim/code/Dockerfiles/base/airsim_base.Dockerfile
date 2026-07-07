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

# Application dependencies [airsim ros wrapper]
RUN apt-get install -yqq --no-install-recommends libopencv-dev libyaml-cpp-dev \
    ros-noetic-tf2-ros ros-noetic-tf2-sensor-msgs ros-noetic-tf2-geometry-msgs \
    ros-noetic-cv-bridge ros-noetic-image-transport ros-noetic-mavros-msgs ros-noetic-pcl-ros \
    && echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> ~/.bashrc \
    && echo "source /opt/ros/$ROS_DISTRO/setup.zsh" >> ~/.zshrc 

# Application dependencies [assets simulator]
RUN apt-get install -yqq --no-install-recommends python3 python3-pip python3-dev python3-setuptools python3-wheel python3-apt \
    && pip3 install --upgrade pip \
    && pip3 install numpy \
    && pip3 install scipy pynput msgpack-rpc-python matplotlib

# Clean up
RUN apt-get autoremove -yqq && apt-get autoclean -yqq

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /root

# Install application [airsim ros wrapper]
COPY airsim /root/airsim
COPY airsim_ros_wrapper /root/airsim_ws/src/airsim_ros_wrapper
RUN cd airsim && ./setup.sh && ./build.sh  && cd .. \
    && source /opt/ros/$ROS_DISTRO/setup.bash \
    && cd airsim_ws \
    && catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
    && cd build && make install \
    && cd /root && rm -r /root/airsim && rm -r /root/airsim_ws/ 

# Install application [assets simulator]
COPY colibri_state_machine_msgs /root/colibri_state_machine_msgs_ws/src/colibri_state_machine_msgs
RUN cd /root/colibri_state_machine_msgs_ws \
    && source /opt/ros/$ROS_DISTRO/setup.bash \
    && catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
    && cd build && make install \
    && cd /root && rm -r /root/colibri_state_machine_msgs_ws
COPY airsim/PythonClient /root/PythonClient
RUN  cd PythonClient/ && pip3 install . && cd /root && rm -r /root/PythonClient
COPY airsim_assets_manager/airsim_assets_manager.py /root/airsim_assets_manager.py
COPY airsim_assets_manager/fleet_simulator.py /root/fleet_simulator.py

# Default command
CMD ["zsh"]