#!/bin/bash
PREFIX="\033[0;34m[Build Script]\033[0m"
# Debug message
echo -e "${PREFIX} Building the project"
# Run the project
bazel-5.3.0 run //main:limewire
# Debug message
echo -e "${PREFIX} Success"