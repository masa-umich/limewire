#!/bin/bash
PREFIX="\033[0;34m[Build Script]\033[0m"
# Debug message
echo -e "${PREFIX} Building the project"
# Build the project
bazel-5.3.0 build //main:limewire
# Debug message
echo -e "${PREFIX} Build successful - copying the binary to project root"
# Copy the binary to the root directory
cp -f build/bin/main/limewire .
# Debug message
echo -e "${PREFIX} Success"