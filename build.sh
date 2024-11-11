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
    --iso-volume "MAGI OS Live" \
    --memtest none \
    --win32-loader false \
    --apt-secure true \
    --apt-source-archives true \
    --debian-installer true \
    --debian-installer-preseedfile true

# Create directories for hooks and includes
echo -e "${BLUE}Creating hook directories...${NC}"
mkdir -p config/hooks/live/
mkdir -p config/includes.chroot/usr/local/bin/
mkdir -p config/debian-installer/

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
    software-properties-common

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

# Install NVIDIA drivers
apt-get install -y \
    nvidia-driver \
    nvidia-settings \
    nvidia-cuda-toolkit \
    firmware-misc-nonfree

# Create Xorg config directory
mkdir -p /etc/X11/xorg.conf.d/

# Configure NVIDIA driver
cat > /etc/X11/xorg.conf.d/10-nvidia.conf << 'XORG'
Section "OutputClass"
    Identifier "NVIDIA"
    MatchDriver "nvidia-drm"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration"
    Option "PrimaryGPU" "yes"
EndSection
XORG

# Configure module loading
cat > /etc/modprobe.d/nvidia.conf << 'MODPROBE'
options nvidia-drm modeset=1
options nvidia NVreg_PreserveVideoMemoryAllocations=1
MODPROBE

# Create driver detection script
cat > /usr/local/sbin/nvidia-driver-setup << 'SCRIPT'
#!/bin/bash
set -e

# Load nvidia module with modeset
modprobe nvidia-drm modeset=1

# Detect GPU
gpu_name=$(lspci -nn | grep -i nvidia | head -n1)
echo "Detected GPU: $gpu_name"

# Configure Prime if needed (for laptops with hybrid graphics)
if lspci | grep -i intel > /dev/null && lspci | grep -i nvidia > /dev/null; then
    echo "Hybrid graphics detected, configuring PRIME..."
    prime-select nvidia
fi

# Update initramfs to include nvidia modules
update-initramfs -u

# Restart display manager if it's running
if systemctl is-active --quiet display-manager; then
    systemctl restart display-manager
fi
SCRIPT

chmod +x /usr/local/sbin/nvidia-driver-setup

# Create systemd service
cat > /etc/systemd/system/nvidia-driver-setup.service << 'SERVICE'
[Unit]
Description=NVIDIA Driver Setup
Before=display-manager.service
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/nvidia-driver-setup
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE

# Enable the service
systemctl enable nvidia-driver-setup.service

# Configure initramfs
cat > /etc/initramfs-tools/conf.d/nvidia.conf << 'INITRAMFS'
MODULES=most
MODULESDIR=/lib/modules
INITRAMFS

# Update initramfs
update-initramfs -u -k all

echo "NVIDIA driver installation and configuration completed"
EOF

chmod +x config/hooks/live/nvidia.hook.chroot

# Create MAGI installation script
echo -e "${BLUE}Creating MAGI installation scripts...${NC}"
cat > config/includes.chroot/usr/local/bin/install-magi << 'EOF'
#!/bin/bash
set -e

# Clone MAGI repository
git clone https://github.com/yourusername/magi /opt/magi
cd /opt/magi
./setup.sh

# Create update script
cat > /usr/local/bin/update-magi << 'UPDATE'
#!/bin/bash
set -e
cd /opt/magi
git pull
./setup.sh
apt-get update && apt-get upgrade -y
UPDATE

chmod +x /usr/local/bin/update-magi
EOF

chmod +x config/includes.chroot/usr/local/bin/install-magi

# Create installer configuration
echo -e "${BLUE}Creating installer configuration...${NC}"
cat > config/debian-installer/preseed.cfg << 'EOF'
# Basic system configuration
d-i debian-installer/locale string en_US.UTF-8
d-i keyboard-configuration/xkb-keymap select us
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string magi
d-i netcfg/get_domain string localdomain

# Partitioning
d-i partman-auto/method string regular
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

# Package selection
tasksel tasksel/first multiselect standard
d-i pkgsel/include string openssh-server

# Boot loader installation
d-i grub-installer/only_debian boolean true
d-i grub-installer/bootdev string default
d-i grub-installer/with_other_os boolean true

# Finishing up
d-i finish-install/reboot_in_progress note
EOF

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
