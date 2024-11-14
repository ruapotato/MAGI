#!/bin/bash
# in_chroot.sh - Sets up the chroot environment for MAGI OS
set -e

# Install desktop environment and dependencies
apt-get update
apt-get install -y \
    pciutils \
    kmod \
    linux-headers-amd64 \
    build-essential \
    dkms \
    pkg-config \
    xserver-xorg \
    xserver-xorg-core \
    xserver-xorg-input-all \
    xserver-xorg-video-all \
    xfonts-base \
    xinit \
    x11-xserver-utils \
    x11-utils \
    x11-common \
    dbus-x11 \
    curl \
    wget \
    gnupg \
    ca-certificates \
    mate-desktop-environment \
    mate-desktop-environment-extras \
    mate-terminal \
    mate-power-manager \
    mate-polkit \
    gdm3 \
    python3-pip \
    python3-venv \
    python3-gi \
    python3-gi-cairo \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    libgirepository1.0-dev \
    pkg-config \
    libcairo2-dev \
    libportaudio2 \
    portaudio19-dev \
    gir1.2-gtk-3.0 \
    gir1.2-wnck-3.0 \
    adwaita-icon-theme \
    dbus-x11 \
    at-spi2-core \
    xdotool \
    espeak \
    feh \
    xcompmgr \
    rofi \
    alacritty \
    network-manager \
    network-manager-gnome \
    pulseaudio \
    pavucontrol

# Create NVIDIA detection and setup script
cat > /usr/local/bin/nvidia-live-setup << 'EOF'
#!/bin/bash

NVIDIA_DETECT_LOG="/var/log/nvidia-detect.log"
DRIVER_DIR="/opt/nvidia-drivers"

echo "Starting NVIDIA GPU detection..." | tee -a "$NVIDIA_DETECT_LOG"

# Detect NVIDIA card
gpu_info=$(lspci -nn | grep -i nvidia)
if [ -z "$gpu_info" ]; then
    echo "No NVIDIA GPU detected" | tee -a "$NVIDIA_DETECT_LOG"
    exit 0
fi

device_id=$(echo "$gpu_info" | grep -oP "10de:\K[0-9a-f]{4}")
echo "Detected NVIDIA GPU with device ID: $device_id" | tee -a "$NVIDIA_DETECT_LOG"

# Load version mapping
if [ -f "/opt/nvidia-drivers/versions.conf" ]; then
    driver_version=$(grep "^$device_id:" /opt/nvidia-drivers/versions.conf | cut -d: -f2 | tr -d ' ')
    if [ -z "$driver_version" ]; then
        driver_version=$(grep "DEFAULT:" /opt/nvidia-drivers/versions.conf | cut -d: -f2 | tr -d ' ')
    fi
else
    # Default to latest stable if no mapping exists
    driver_version=$(ls /opt/nvidia-drivers/nvidia-driver_* 2>/dev/null | sort -V | tail -n1 | grep -oP '\d+\.\d+\.\d+-\d+' || echo "")
fi

if [ -z "$driver_version" ]; then
    echo "No suitable driver found" | tee -a "$NVIDIA_DETECT_LOG"
    exit 1
fi

echo "Installing NVIDIA driver version $driver_version..." | tee -a "$NVIDIA_DETECT_LOG"

# Install drivers in correct order
packages=(
    "nvidia-kernel-support"
    "nvidia-kernel-dkms"
    "nvidia-driver-libs"
    "nvidia-driver"
    "xserver-xorg-video-nvidia"
)

for pkg in "${packages[@]}"; do
    if [ -f "$DRIVER_DIR/${pkg}_${driver_version}_amd64.deb" ]; then
        echo "Installing $pkg..." | tee -a "$NVIDIA_DETECT_LOG"
        dpkg -i "$DRIVER_DIR/${pkg}_${driver_version}_amd64.deb" || true
    fi
done

# Fix dependencies
apt-get install -f -y

# Configure modules
echo "Configuring NVIDIA modules..." | tee -a "$NVIDIA_DETECT_LOG"
cat > /etc/modprobe.d/nvidia.conf << 'MODCONF'
options nvidia-drm modeset=1
options nvidia NVreg_PreserveVideoMemoryAllocations=1
options nvidia NVreg_RegistryDwords="EnableBrightnessControl=1"
MODCONF

cat > /etc/modules-load.d/nvidia.conf << 'MODLOAD'
nvidia
nvidia_drm
nvidia_uvm
nvidia_modeset
MODLOAD

# Blacklist nouveau
echo "Blacklisting nouveau..." | tee -a "$NVIDIA_DETECT_LOG"
cat > /etc/modprobe.d/blacklist-nouveau.conf << 'NOUVEAU'
blacklist nouveau
blacklist lbm-nouveau
blacklist rivafb
blacklist nvidiafb
blacklist rivatv
options nouveau modeset=0
alias nouveau off
alias lbm-nouveau off
NOUVEAU

# Configure X.org
mkdir -p /etc/X11/xorg.conf.d/
cat > /etc/X11/xorg.conf.d/10-nvidia.conf << 'XORG'
Section "OutputClass"
    Identifier "nvidia"
    MatchDriver "nvidia-drm"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration"
    Option "PrimaryGPU" "yes"
    ModulePath "/usr/lib/x86_64-linux-gnu/nvidia/xorg"
EndSection

Section "ServerLayout"
    Identifier "layout"
    Option "AllowNVIDIAGPUScreens"
EndSection

Section "Device"
    Identifier "nvidia"
    Driver "nvidia"
    Option "NoLogo" "true"
EndSection
XORG

# Update initramfs
update-initramfs -u

# Configure GDM to use X11
if [ -f /etc/gdm3/daemon.conf ]; then
    sed -i 's/#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/daemon.conf
fi

# Try loading modules
modprobe nvidia || true
modprobe nvidia_drm || true
modprobe nvidia_uvm || true
modprobe nvidia_modeset || true

echo "NVIDIA setup completed" | tee -a "$NVIDIA_DETECT_LOG"
EOF

chmod +x /usr/local/bin/nvidia-live-setup

# Create systemd service for NVIDIA setup
cat > /etc/systemd/system/nvidia-live-setup.service << 'EOF'
[Unit]
Description=NVIDIA Driver Setup
Before=display-manager.service
After=systemd-modules-load.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/nvidia-live-setup
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl enable nvidia-live-setup

# Configure GDM3
cat > /etc/gdm3/custom.conf << 'GDM'
[daemon]
WaylandEnable=false
DefaultSession=magi
AutomaticLoginEnable=false
GDM

# Set up Python environment
python3 -m venv /opt/magi/ears_pyenv
source /opt/magi/ears_pyenv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install --no-cache-dir --timeout 100 --retries 3 \
    flask \
    numpy \
    sounddevice \
    requests \
    nvidia-ml-py \
    psutil

pip install --no-cache-dir --timeout 300 --retries 3 \
    torch \
    torchvision \
    torchaudio

pip install --no-cache-dir --timeout 300 --retries 3 \
    transformers \
    "accelerate>=0.26.0" \
    openai-whisper

# Download Whisper model
python3 -c '
import whisper
model = whisper.load_model("base")
'

deactivate

# Install Ollama
curl -fsSL https://ollama.com/install.sh > /tmp/ollama_install.sh
chmod +x /tmp/ollama_install.sh
sh /tmp/ollama_install.sh
rm /tmp/ollama_install.sh

# Create Ollama service
cat > /etc/systemd/system/ollama.service << 'SERVICE'
[Unit]
Description=Ollama Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

# Pull Mistral model
systemctl start ollama
ollama pull mistral

# Create MAGI service
cat > /etc/systemd/system/magi-whisper.service << 'SERVICE'
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
SERVICE

# Create desktop entry
cat > /usr/share/xsessions/magi.desktop << 'DESKTOP'
[Desktop Entry]
Name=MAGI Shell
Comment=Machine Augmented GTK Interface
Exec=/opt/magi/start.sh
Type=Application
DesktopNames=MAGI
DESKTOP

# Enable services
systemctl enable gdm3
systemctl enable NetworkManager
systemctl enable ollama
systemctl enable magi-whisper

# Clean up
apt-get clean
