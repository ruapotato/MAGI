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

# Create directory structure with all required paths
echo "Creating directory structure..."
mkdir -p config/includes.chroot/{etc,opt,usr/local/bin}
mkdir -p config/includes.chroot/etc/{default,modprobe.d,gdm3,skel/.config/magi}
mkdir -p config/includes.chroot/etc/X11/xorg.conf.d
mkdir -p config/includes.chroot/etc/systemd/system
mkdir -p config/includes.binary/boot/grub
mkdir -p config/includes.chroot/usr/share/{magi/backgrounds,xsessions}
mkdir -p config/includes.chroot/opt/{magi,nvidia-drivers}
mkdir -p config/includes.chroot/tmp/MAGI

# Set permissions for MAGI directory
chmod 777 config/includes.chroot/tmp/MAGI

# Set repository URL and get available drivers
REPO_URL="https://deb.debian.org/debian/pool/non-free-firmware/n/nvidia-graphics-drivers/"
echo "Getting available NVIDIA packages..."

# Get all package names and extract the latest versions from the firmware packages
NVIDIA_VERSIONS=$(curl -s "$REPO_URL" | \
    grep -o 'href="[^"]*deb"' | \
    cut -d'"' -f2 | \
    grep '^firmware-nvidia-gsp_' | \
    grep '_amd64.deb$' | \
    sed 's/firmware-nvidia-gsp_\(.*\)_amd64.deb/\1/' | \
    sort -V | \
    tail -n 2)

if [ -z "$NVIDIA_VERSIONS" ]; then
    echo "Error: Could not find any NVIDIA drivers"
    exit 1
fi

echo "Found driver versions: $NVIDIA_VERSIONS"

# Convert to array and get latest version
readarray -t DRIVER_VERSIONS <<< "$NVIDIA_VERSIONS"
LATEST_VERSION="${DRIVER_VERSIONS[-1]}"
echo "Latest version: $LATEST_VERSION"

# Download driver packages for each version
for version in "${DRIVER_VERSIONS[@]}"; do
    echo "Processing driver version: $version"
    
    # Try to download each package type
    packages=(
        "firmware-nvidia-gsp"
        "nvidia-driver"
        "nvidia-kernel-support"
        "nvidia-kernel-dkms"
        "nvidia-driver-libs"
        "xserver-xorg-video-nvidia"
    )
    
    # Base version for library packages (strip revision)
    lib_version=${version%%-*}
    lib_packages=(
        "libnvidia-encode-${lib_version}"
        "libnvidia-compute-${lib_version}"
    )
    
    # Try base packages
    for pkg in "${packages[@]}"; do
        package_name="${pkg}_${version}_amd64.deb"
        package_url="${REPO_URL}${package_name}"
        echo "Trying to download: $package_name"
        
        wget --quiet --spider "$package_url" 2>/dev/null && {
            echo "Found package! Downloading $package_name..."
            wget --quiet --show-progress -P config/includes.chroot/opt/nvidia-drivers/ \
                "$package_url" && \
                echo "Successfully downloaded $package_name" || \
                echo "Failed to download $package_name"
        }
    done
    
    # Try library packages
    for pkg in "${lib_packages[@]}"; do
        package_name="${pkg}_${version}_amd64.deb"
        package_url="${REPO_URL}${package_name}"
        echo "Trying to download: $package_name"
        
        wget --quiet --spider "$package_url" 2>/dev/null && {
            echo "Found package! Downloading $package_name..."
            wget --quiet --show-progress -P config/includes.chroot/opt/nvidia-drivers/ \
                "$package_url" && \
                echo "Successfully downloaded $package_name" || \
                echo "Failed to download $package_name"
        }
    done
done


# Copy MAGI files
echo "Copying MAGI files..."
git clone https://github.com/ruapotato/MAGI ./config/includes.chroot/opt/magi/


# Ensure all files are executable
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

# Create startup scripts
cat > config/includes.chroot/opt/magi/start_whisper_server.sh << 'EOF'
#!/bin/bash
source /opt/magi/ears_pyenv/bin/activate
export PYTHONPATH=/opt/magi/ears_pyenv/lib/python3.11/site-packages
exec python3 /opt/magi/server.py
EOF

# Set permissions
chmod +x config/includes.chroot/opt/magi/*.sh
chmod +x config/includes.chroot/opt/magi/*.py

# Generate version mapping file
cat > config/includes.chroot/opt/nvidia-drivers/versions.conf << EOF
# GPU Model to Driver Version mapping
# Format: GPU_ID:DRIVER_VERSION
# Last updated: $(date)

# Using latest version: ${LATEST_VERSION}
DEFAULT:${LATEST_VERSION}
EOF

# Create systemd service files
cat > config/includes.chroot/etc/systemd/system/magi-whisper.service << 'EOF'
[Unit]
Description=MAGI Whisper Speech Recognition Server
After=network.target

[Service]
Type=simple
User=root
ExecStart=/opt/magi/start_whisper_server.sh
WorkingDirectory=/opt/magi
Restart=always
RestartSec=3
Environment="PYTHONPATH=/opt/magi/ears_pyenv/lib/python3.11/site-packages"

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for Ollama
cat > config/includes.chroot/etc/systemd/system/ollama.service << 'EOF'
[Unit]
Description=Ollama Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Environment="HOME=/var/lib/ollama"
ExecStart=/usr/local/bin/ollama serve
WorkingDirectory=/var/lib/ollama
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Create pre-start script to verify model
cat > config/includes.chroot/usr/local/bin/verify-ollama-model << 'EOF'
#!/bin/bash

MODELS_DIR="/var/lib/ollama/models"
MANIFESTS_DIR="/var/lib/ollama/manifests"

# Wait for Ollama service to be ready
sleep 5

# Check if model files exist
if [ -d "$MODELS_DIR/blobs" ] && [ -d "$MANIFESTS_DIR/registry.ollama.ai/library/mistral" ]; then
    # Force Ollama to recognize the model
    ollama list >/dev/null 2>&1
    if ! ollama list | grep -q "mistral"; then
        echo "Model files exist but not registered. Attempting to repair..."
        systemctl restart ollama
        sleep 5
    fi
fi
EOF
chmod +x config/includes.chroot/usr/local/bin/verify-ollama-model

# Create service to verify model at startup
cat > config/includes.chroot/etc/systemd/system/verify-ollama-model.service << 'EOF'
[Unit]
Description=Verify Ollama Model Presence
After=ollama.service
Before=magi-session.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/verify-ollama-model
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

cat > config/includes.chroot/etc/systemd/system/magi-session.service << 'EOF'
[Unit]
Description=MAGI Session Service
After=gdm3.service

[Service]
Type=simple
ExecStart=/opt/magi/start.sh
User=magi
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/magi/.Xauthority

[Install]
WantedBy=graphical.target
EOF

# Create default config for MAGI
cat > config/includes.chroot/etc/skel/.config/magi/config.json << 'EOF'
{
    "panel_height": 28,
    "workspace_count": 4,
    "enable_effects": true,
    "enable_ai": true,
    "terminal": "mate-terminal",
    "launcher": "mate-panel --run-dialog",
    "background": "/usr/share/magi/backgrounds/default.png",
    "ollama_model": "mistral",
    "whisper_endpoint": "http://localhost:5000/transcribe",
    "sample_rate": 16000
}
EOF

# Create GDM configuration
cat > config/includes.chroot/etc/gdm3/custom.conf << 'EOF'
[daemon]
WaylandEnable=false
DefaultSession=magi
AutomaticLoginEnable=true
AutomaticLogin=magi
InitialSetupEnable=false
EOF

# Create MAGI desktop entry
cat > config/includes.chroot/usr/share/xsessions/magi.desktop << 'EOF'
[Desktop Entry]
Name=MAGI Shell
Comment=Machine Augmented GTK Interface
Exec=/opt/magi/start.sh
Type=Application
DesktopNames=MAGI
EOF

# Create hooks directory if it doesn't exist
mkdir -p config/hooks/live/

# Note: The in_chroot.sh script should be copied to hooks by the main build script
chmod +x config/hooks/live/*.hook.chroot

echo "Base system configuration completed successfully"
