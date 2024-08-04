#!/bin/bash

# Create the build directory if it doesn't exist
mkdir -p build

# Change to the build directory
cd build

# Run CMake to generate the build files
cmake ..

# Run the build command (e.g., make)
cmake --build .