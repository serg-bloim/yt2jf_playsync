#!/bin/bash

# Set repo URL and target directory
REPO_URL="https://github.com/serg-bloim/yt2jf_playsync.git"
REPO_NAME="yt2jf_playsync"

echo Removing the existing git repo if any
rm -rf "$REPO_NAME"

all_versions=$(git ls-remote --tags --sort='v:refname' https://github.com/serg-bloim/yt2jf_playsync.git 'v*' | cut -d/ -f3-)
echo "Available versions:"
echo "$all_versions"

version=$(echo "$all_versions" | tail -n1)
echo "Latest version is: $version"

# Clone the repository
echo "Cloning repository..."
git clone --depth=1 --branch="$version" "$REPO_URL"
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
