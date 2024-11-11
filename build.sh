#!/bin/bash

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
        # Clean up any partial build artifacts
        if [ -d "magi-os-build" ]; then
            echo -e "${YELLOW}Cleaning up failed build...${NC}"
            cd magi-os-build 2>/dev/null && sudo lb clean 2>/dev/null || true
        fi
    fi
}

echo -e "${BLUE}Setting up MAGI OS build environment...${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Clean up existing build if found
if [ -d "magi-os-build" ]; then
    echo -e "${YELLOW}Existing build directory found. Cleaning up...${NC}"
    cd magi-os-build
    lb clean
    cd ..
    rm -rf magi-os-build
fi

# Create fresh build directory structure
echo -e "${BLUE}Creating build directory structure...${NC}"
mkdir -p magi-os-build/{cache,config,output,work}
cd magi-os-build

# Install or update required tools
echo -e "${BLUE}Installing/updating required packages...${NC}"
apt-get update
apt-get install -y \
    debootstrap \
    squashfs-tools \
    xorriso \
    grub-efi-amd64-bin \
    mtools \
    apt-utils \
    curl \
    git \
    isolinux \
    syslinux-common \
    live-build \
    nvidia-detect \
    wget \
    gnupg \
    software-properties-common

# Create base live-build config
echo -e "${BLUE}Configuring live-build...${NC}"
lb config \
    --architecture amd64 \
    --distribution bookworm \
    --debian-installer live \
    --debian-installer-gui true \
    --archive-areas "main contrib non-free non-free-firmware" \
    --security true \
    --updates true \
    --backports true \
    --binary-images iso-hybrid \
    --iso-publisher "MAGI OS" \
    --iso-volume "MAGI OS" \
    --memtest none \
    --win32-loader false \
    --apt-secure true \
    --apt-source-archives true \
    --debian-installer true \
    --debian-installer-preseedfile true

# Create directories for hooks and includes
echo -e "${BLUE}Creating hook directories...${NC}"
mkdir -p config/hooks/live/
mkdir -p config/includes.chroot/etc/default/
mkdir -p config/includes.chroot/etc/modprobe.d/
mkdir -p config/includes.binary/boot/grub/
mkdir -p config/includes.chroot/usr/local/bin/
mkdir -p config/debian-installer/

# Create GRUB customization
echo -e "${BLUE}Customizing GRUB...${NC}"
cat > config/includes.binary/boot/grub/theme.txt << 'EOF'
desktop-image: "background.png"
title-text: "MAGI OS"
title-color: "#7aa2f7"
title-font: "DejaVu Sans Bold 16"
message-font: "DejaVu Sans 12"
terminal-font: "DejaVu Sans Mono 12"

+ boot_menu {
    left = 15%
    width = 70%
    top = 20%
    height = 60%
    item_font = "DejaVu Sans 12"
    item_color = "#c0caf5"
    selected_item_color = "#7aa2f7"
    item_height = 24
    item_padding = 5
    item_spacing = 1
}

+ progress_bar {
    id = "__timeout__"
    left = 15%
    width = 70%
    top = 85%
    height = 16
    show_text = true
    font = "DejaVu Sans 12"
    text_color = "#7aa2f7"
    fg_color = "#7aa2f7"
    bg_color = "#1a1b26"
    border_color = "#565f89"
}
EOF

# Create GRUB default configuration
cat > config/includes.chroot/etc/default/grub << 'EOF'
GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_DISTRIBUTOR="MAGI"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash nouveau.modeset=0 rd.driver.blacklist=nouveau nvidia-drm.modeset=1"
GRUB_CMDLINE_LINUX=""
GRUB_BACKGROUND="/usr/share/magi/backgrounds/default.png"
GRUB_THEME="/boot/grub/theme.txt"
EOF

# Create nouveau blacklist
cat > config/includes.chroot/etc/modprobe.d/blacklist-nouveau.conf << 'EOF'
blacklist nouveau
blacklist lbm-nouveau
options nouveau modeset=0
alias nouveau off
alias lbm-nouveau off
EOF

# Create NVIDIA driver hook
echo -e "${BLUE}Creating NVIDIA configuration...${NC}"
cat > config/hooks/live/nvidia.hook.chroot << 'EOF'
#!/bin/bash
set -e

# Ensure prerequisites are installed
apt-get update
apt-get install -y \
    curl \
    wget \
    gnupg \
    software-properties-common \
    dkms \
    build-essential \
    linux-headers-amd64

# Enable non-free and contrib repositories
cat > /etc/apt/sources.list << 'SOURCES'
deb http://deb.debian.org/debian/ bookworm main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian/ bookworm-updates main contrib non-free non-free-firmware
SOURCES

# Add NVIDIA CUDA repository
wget https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb
rm cuda-keyring_1.1-1_all.deb

# Update package lists
apt-get update

# Install NVIDIA drivers with DKMS support
apt-get install -y \
    nvidia-driver \
    nvidia-settings \
    nvidia-cuda-toolkit \
    firmware-misc-nonfree

# Ensure nouveau is blacklisted
cat > /etc/modprobe.d/blacklist-nouveau.conf << 'BLACKLIST'
blacklist nouveau
blacklist lbm-nouveau
options nouveau modeset=0
alias nouveau off
alias lbm-nouveau off
BLACKLIST

# Configure NVIDIA driver loading
cat > /etc/modprobe.d/nvidia.conf << 'MODPROBE'
options nvidia-drm modeset=1
options nvidia NVreg_PreserveVideoMemoryAllocations=1
MODPROBE

# Create custom X11 configuration for NVIDIA
mkdir -p /etc/X11/xorg.conf.d/
cat > /etc/X11/xorg.conf.d/10-nvidia.conf << 'XORG'
Section "OutputClass"
    Identifier "NVIDIA"
    MatchDriver "nvidia-drm"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration"
    Option "PrimaryGPU" "yes"
    Option "ModulePath" "/usr/lib/x86_64-linux-gnu/nvidia/xorg"
EndSection

Section "Device"
    Identifier "NVIDIA Card"
    Driver "nvidia"
    Option "NoLogo" "true"
EndSection
XORG

# Update initramfs to apply changes
update-initramfs -u -k all

# Create display manager configuration for NVIDIA
mkdir -p /etc/gdm3
cat > /etc/gdm3/custom.conf << 'GDM'
[daemon]
WaylandEnable=false
DefaultSession=magi
GDM

# Clean up
apt-get clean
EOF

chmod +x config/hooks/live/nvidia.hook.chroot

# Build the ISO
echo -e "${BLUE}Starting ISO build...${NC}"
lb build 2>&1 | tee build.log

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}Build completed successfully!${NC}"
    echo -e "${BLUE}ISO location: ${NC}$(pwd)/live-image-amd64.hybrid.iso"
    echo -e "${BLUE}Build log: ${NC}$(pwd)/build.log"
else
    echo -e "${RED}Build failed! Check build.log for details${NC}"
    exit 1
fi

# Create SHA256 checksum
sha256sum live-image-amd64.hybrid.iso > live-image-amd64.hybrid.iso.sha256

echo -e "${GREEN}Build process completed!${NC}"
echo -e "${BLUE}To verify the ISO:${NC}"
echo "sha256sum -c live-image-amd64.hybrid.iso.sha256"
