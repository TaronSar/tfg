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

# Application dependencies [UAL / colibri state machine / target_detector]
RUN apt-get install -yqq --no-install-recommends libyaml-cpp-dev python-is-python3 python3-pip python3-tk ros-noetic-smach-ros \
    ros-noetic-joy ros-noetic-geodesy ros-noetic-mavros ros-noetic-mavros-extras ros-noetic-tf2-geometry-msgs \
    && apt-get remove modemmanager -yqq\
    && geographiclib-get-geoids egm96-5 \
    && echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> ~/.bashrc \
    && echo "source /opt/ros/$ROS_DISTRO/setup.zsh" >> ~/.zshrc

# Clean up
RUN apt-get autoremove -yqq && apt-get autoclean -yqq

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /root

# Install application [UAL]
COPY grvc-ual/ /root/ual_ws/src/grvc-ual/
RUN cd ual_ws/ && source /opt/ros/$ROS_DISTRO/setup.bash \
&& catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
&& cd build && make install \
&& cd /root && rm -r /root/ual_ws

# Install application [target_detector]
COPY aruco_ros_detector /root/target_detector_ws/src/aruco_ros_detector
RUN export DEBIAN_FRONTEND=noninteractive \
&& rosdep update  \
&& rosdep install --from-paths -y --ignore-src -r /root/target_detector_ws/src/aruco_ros_detector \
&& cd target_detector_ws/ && source /opt/ros/$ROS_DISTRO/setup.bash \
&& catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
&& cd build && make install \
&& cd /root && rm -r /root/target_detector_ws

# Install application [colibri state machine]
COPY colibri_state_machine/ /root/sm_ws/src/colibri_state_machine/
COPY colibri_state_machine_msgs/ /root/sm_ws/src/colibri_state_machine_msgs/
COPY land_control/ /root/sm_ws/src/land_control/
COPY grvc-ual/uav_abstraction_layer/ /root/sm_ws/src/uav_abstraction_layer/
RUN export DEBIAN_FRONTEND=noninteractive \
    && rosdep update  \
    && rosdep install --from-paths -y /root/sm_ws/src/land_control \
    && rosdep install --from-paths -y /root/sm_ws/src/uav_abstraction_layer \
    && cd sm_ws/ && source /opt/ros/$ROS_DISTRO/setup.bash \
    && catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
    && cd build && make install \
    && cd /root && rm -r /root/sm_ws

# Default command 
CMD ["zsh"]