FROM airsim:latest

SHELL ["/bin/bash", "-c"]
WORKDIR /root

# Replace AirSim source with local version.
COPY airsim /root/airsim

# Install AirSim dependencies (~5-10 min).
RUN cd /root/airsim && ./setup.sh

# Compile AirSim C++ (~30-60 min). Cached separately so ROS wrapper failures don't require a full rebuild.
RUN cd /root/airsim \
    && rm -rf cmake_build build_release \
    && ./build.sh --gcc

# Build and install the ROS wrapper (~5-15 min).
RUN source /opt/ros/$ROS_DISTRO/setup.bash \
    && if [ -d /root/airsim_ws/src/airsim_ros_wrapper ]; then \
        cd /root/airsim_ws \
        && catkin_make -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/$ROS_DISTRO \
        && cd build \
        && make install; \
       else \
        echo "airsim_ros_wrapper source not found in base image; keeping preinstalled package"; \
       fi

# Install the patched AirSim Python client from local sources.
RUN python3 -m pip uninstall -y airsim || true \
    && python3 -m pip install --no-cache-dir /root/airsim/PythonClient \
    && python3 -c 'import airsim; assert hasattr(airsim.MultirotorClient, "moveByMotorVectorPWMsAsync"), "Patched AirSim PythonClient missing moveByMotorVectorPWMsAsync"; print("AirSim PythonClient OK:", airsim.__file__)'

# Remove build sources to reduce final image size.
RUN rm -rf /root/airsim /root/airsim_ws

RUN pip3 install loguru
RUN pip3 install typing_extensions