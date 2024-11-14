#!/bin/bash
# setup_base.sh - Sets up the base system configuration for MAGI OS

set -e

# Install required tools
echo "Installing required packages..."
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

# Configure live-build
echo "Configuring live-build..."
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

# Create directory structure
echo "Creating directory structure..."
mkdir -p config/includes.chroot/{etc,opt,usr/local/bin}
mkdir -p config/includes.chroot/etc/{default,modprobe.d,gdm3,skel/.config/magi}
mkdir -p config/includes.binary/boot/grub/
mkdir -p config/includes.chroot/usr/share/magi/backgrounds
mkdir -p config/includes.chroot/opt/magi/
mkdir -p config/includes.chroot/opt/nvidia-drivers/

# Create NVIDIA driver cache directory
echo "Downloading NVIDIA drivers..."
NVIDIA_DRIVERS=(
    "535.216.01-1"  # Latest
    "525.147.05-7"  # Legacy
    "470.256.02-2"  # Legacy
)

for version in "${NVIDIA_DRIVERS[@]}"; do
    echo "Downloading NVIDIA driver version $version..."
    
    packages=(
        "nvidia-driver"
        "nvidia-kernel-support"
        "nvidia-kernel-dkms"
        "nvidia-driver-libs"
        "xserver-xorg-video-nvidia"
        "libnvidia-encode"
        "libnvidia-compute"
    )
    
    for pkg in "${packages[@]}"; do
        wget -q -P config/includes.chroot/opt/nvidia-drivers/ \
            "http://deb.debian.org/debian/pool/non-free-firmware/n/nvidia-graphics-drivers/${pkg}_${version}_amd64.deb" || \
            echo "Warning: Failed to download ${pkg}_${version}"
    done
done

# Create version mapping file
cat > config/includes.chroot/opt/nvidia-drivers/versions.conf << 'EOF'
# GPU Model to Driver Version mapping
# Format: GPU_ID:DRIVER_VERSION

# Legacy GPUs (470 series)
0FC0:470.256.02-2  # GT 710
0FC1:470.256.02-2  # GT 730
1180:470.256.02-2  # GTX 680
1183:470.256.02-2  # GTX 660

# Modern GPUs (525 series)
1B80:525.147.05-7  # GTX 1080
1B81:525.147.05-7  # GTX 1070
1B84:525.147.05-7  # GTX 1060 3GB
1B83:525.147.05-7  # GTX 1060 6GB

# Latest GPUs (535 series)
2204:535.216.01-1  # RTX 3090
2206:535.216.01-1  # RTX 3080
2208:535.216.01-1  # RTX 3070
2684:535.216.01-1  # RTX 4090
2782:535.216.01-1  # RTX 4080

# Default for unknown cards
DEFAULT:535.216.01-1
EOF

# Copy MAGI files
echo "Copying MAGI files..."
cp ../magi_shell.py config/includes.chroot/opt/magi/
cp ../server.py config/includes.chroot/opt/magi/
cp ../llm_menu.py config/includes.chroot/opt/magi/

# Create startup scripts
cat > config/includes.chroot/opt/magi/start.sh << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export DISPLAY=:0
export XAUTHORITY="$HOME/.Xauthority"
exec python3 "$SCRIPT_DIR/magi_shell.py"
EOF

cat > config/includes.chroot/opt/magi/start_whisper_server.sh << 'EOF'
#!/bin/bash
source /opt/magi/ears_pyenv/bin/activate
export PYTHONPATH=/opt/magi/ears_pyenv/lib/python3.11/site-packages
exec python3 /opt/magi/server.py
EOF

# Set permissions
chmod +x config/includes.chroot/opt/magi/*.sh
chmod +x config/includes.chroot/opt/magi/*.py

# Create GRUB theme
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

# Create GRUB configuration
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

# Create NVIDIA configuration
mkdir -p config/includes.chroot/etc/X11/xorg.conf.d/
cat > config/includes.chroot/etc/X11/xorg.conf.d/10-nvidia.conf << 'EOF'
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
EOF
