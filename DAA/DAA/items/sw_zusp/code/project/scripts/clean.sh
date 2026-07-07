#!/bin/bash

cd ../cmake/

echo "Cleaning ZUSp library ..."

if [ ! -d "build" ]
then
    rm -r build
fi
