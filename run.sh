#!/bin/bash
PREFIX="\033[0;34m[Build Script]\033[0m"

# Run the project
echo -e "${PREFIX} Running Limewire"
bazel run //main:limewire
# linux command is bazel-5.3.0 run //main:limewire

# Check if build failed
EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
    echo -e "${PREFIX} Build Unsuccessful (Code ${EXIT_CODE})"
    exit $EXIT_CODE
fi

# Debug message
echo -e "${PREFIX} Success"
