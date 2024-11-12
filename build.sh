#!/bin/bash
# build.sh - Main orchestration script for MAGI OS build

# Enable error handling
set -e
trap 'catch $? $LINENO' ERR

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Error handling function
catch() {
    if [ "$1" != "0" ]; then
        echo -e "${RED}Error $1 occurred on line $2${NC}"
        if [ -d "magi-os-build" ]; then
            echo -e "${YELLOW}Cleaning up failed build...${NC}"
            cd magi-os-build 2>/dev/null && sudo lb clean 2>/dev/null || true
        fi
    fi
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${BLUE}Starting MAGI OS build process...${NC}"

# Clean up existing build if found
if [ -d "magi-os-build" ]; then
    echo -e "${YELLOW}Existing build directory found. Cleaning up...${NC}"
    cd magi-os-build
    lb clean
    cd ..
    rm -rf magi-os-build
fi

# Create build directory
mkdir -p magi-os-build
cd magi-os-build

# Run base setup script
echo -e "${BLUE}Setting up base system...${NC}"
bash "$SCRIPT_DIR/setup_base.sh"

# Prepare hooks directory
mkdir -p config/hooks/live/

# Create in-chroot script in hooks
echo -e "${BLUE}Setting up chroot environment script...${NC}"
cp "$SCRIPT_DIR/in_chroot.sh" config/hooks/live/mate-setup.hook.chroot
chmod +x config/hooks/live/mate-setup.hook.chroot

# Build the ISO
echo -e "${BLUE}Starting ISO build...${NC}"
lb build 2>&1 | tee build.log

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}Build completed successfully!${NC}"
    echo -e "${BLUE}ISO location: ${NC}$(pwd)/live-image-amd64.hybrid.iso"
    echo -e "${BLUE}Build log: ${NC}$(pwd)/build.log"
    
    # Create SHA256 checksum
    sha256sum live-image-amd64.hybrid.iso > live-image-amd64.hybrid.iso.sha256
    
    echo -e "${GREEN}Build process completed!${NC}"
    echo -e "${BLUE}To verify the ISO:${NC}"
    echo "sha256sum -c live-image-amd64.hybrid.iso.sha256"
else
    echo -e "${RED}Build failed! Check build.log for details${NC}"
    exit 1
fi
