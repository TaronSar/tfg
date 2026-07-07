#!/bin/bash
CROSS_ENV_PATH_SCRIPT=${CROSS_ENVIROMENT}

if [[ -v NOT_CROSS_ENV ]]; then
    CROSS_ENV_PATH_SCRIPT=0
else
echo "CROSS_ENV_PATH ${CROSS_ENV_PATH_SCRIPT}"
fi

DAA_TEXAS=0
COPROC=0
BUILD_TYPE=Release
VIEWER_CLIENT=0
VIEWER_DEBUG=0

echo "Configuring and building KAI ..."

# There is need to checkeout the Vlibs (sw_kai/items/Vlibs) branch to -> feature/DAA/74_vbn

cd /workspace/items/_sw_perception/items/sw_gnssdenied/code/project/scripts && ./cross_build_vlibs.sh

cd /workspace/items/_sw_perception/items/sw_gnssdenied/code/project/scripts && ./cross_build_wvlibs.sh

cd /workspace/items/_sw_perception/items/sw_rtsp/code/project/scripts && ./build.sh

cd /workspace/items/_sw_perception/code/project/scripts && ./cross_build_perception.sh

cd /workspace/items/_sw_perception/items/sw_gnssdenied/code/project/scripts && ./cross_build_streaming.sh && ./cross_build_coproc.sh && ./cross_build_orb_slam3.sh

cd /workspace/code/main1/code/project/scripts/ && ./cross_build_lm.sh main1/code/

cd /workspace/code/main1/code/project/cmake/build/ && mv lm sw_kai

# OUTPUT INTO --> /workspace/code/main1/code/project/cmake/build/
