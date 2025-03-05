#!/bin/bash

# Set repo URL and target directory
REPO_URL="https://github.com/serg-bloim/yt2jf_playsync.git"
REPO_NAME="yt2jf_playsync"
# Clone the repository
echo "Cloning repository..."
git clone --depth=1 "$REPO_URL"
# Check if the repo was cloned successfully
if [ ! -d "$REPO_NAME" ]; then
    echo "Error: Failed to clone repository!"
    exit 1
fi
# Navigate into the repo directory
cd "$REPO_NAME" || exit
# Make sure the script is executable
chmod +x docker.build.sh
# Run the build script
echo "Running docker.build.sh..."
./docker.build.sh
