#!/bin/bash
PREFIX="\033[0;34m[Build Script]\033[0m"
echo -e "${PREFIX} Building Limewire..."

# Build the project
bazel-5.3.0 build -c dbg //main:limewire

# Check if build failed
EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
    echo -e "${PREFIX} Build Unsuccessful (Code ${EXIT_CODE})"
    exit $EXIT_CODE
fi

# Copy the binary to the root directory
echo -e "${PREFIX} Build Successful! Copying binary to project root..."
cp -f build/bin/main/limewire .

echo -e "${PREFIX} Success"
