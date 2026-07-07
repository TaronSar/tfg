# Documentation for primary installations, Docker container set-up and 
# running/compiling processes

# 1. Docker install on computer (Ubuntu):
https://docs.docker.com/engine/install/ubuntu/


# 2. Nvidia-docker install on computer (Ubuntu):
https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html


# 3. CUDA installing process (v12.3):
https://developer.nvidia.com/cuda-12-3-0-download-archive



# --------------------	SET-UP OF DOCKER, AND COMPILATION/RUNNING -----------------------

# 4. Go to: .../DAA/items/sw_gnssdenied/code/projects/docker (after cloning repository from Github)
#    Execute: ./build.sh


#		POSSIBLE ERROR CASES (DOCKERFILE ASSOCIATED TO BUILD.SH):
# > In the 'Dockerfile' archive, check 'git' dependency in Pangolin Dependencies
# > In case that /usr/local/include/sophus doesn't exist, eliminate line
#   'RUN rm -r /usr/local/include/sophus' (or comment it)
# > Where there's a command of 'RUN apt-get update -y && ...', add
#   the following: 'apt-get install -y python3 python3-pip' at the end


# 5. Run ./run.sh in terminal (file in the same folder of above)


# 6. Inside the docker container, go to: .../workspace/items/sw_gnssdenied/code/project/scripts
#    Run for instance the file: ./build_in_container_arm.sh
