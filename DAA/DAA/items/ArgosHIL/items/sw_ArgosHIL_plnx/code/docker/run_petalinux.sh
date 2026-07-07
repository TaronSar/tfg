#!/bin/bash

echo "🚀 Arrancando cápsula de PetaLinux (Ubuntu 22.04)..."
echo "📂 Montando volúmenes y accediendo al proyecto..."

docker run -ti --rm \
  -v /tools/petalinux2023:/tools/petalinux2023 \
  -v /home/ijm1/DAA/items/:/home/ijm1/DAA/items/ \
  -w /home/ijm1/DAA/items/ \
  petalinux_2204_env /bin/bash