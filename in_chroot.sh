#!/bin/bash
# in_chroot.sh - Sets up the chroot environment for MAGI OS
set -e

# Install desktop environment and dependencies
apt-get update
apt-get install -y \
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


setup_nvidia() {
    echo "Setting up NVIDIA drivers for modern GPUs..."

    # Add non-free repositories
    cat > /etc/apt/sources.list << 'SOURCES'
deb http://deb.debian.org/debian/ bookworm main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian/ bookworm-updates main contrib non-free non-free-firmware
SOURCES

    # Update package lists
    apt-get update

    # Install essential packages
    apt-get install -y \
        linux-headers-amd64 \
        build-essential \
        dkms \
        pkg-config

    # Install NVIDIA drivers - explicitly specify version
    apt-get install -y \
        nvidia-kernel-common \
        nvidia-driver \
        nvidia-kernel-dkms \
        firmware-misc-nonfree

    # Create module configuration
    cat > /etc/modprobe.d/nvidia.conf << 'EOF'
options nvidia-drm modeset=1
options nvidia NVreg_PreserveVideoMemoryAllocations=1
options nvidia NVreg_RegistryDwords="EnableBrightnessControl=1"
EOF

    # Blacklist nouveau
    cat > /etc/modprobe.d/blacklist-nouveau.conf << 'EOF'
blacklist nouveau
blacklist lbm-nouveau
blacklist rivafb
blacklist nvidiafb
blacklist rivatv
options nouveau modeset=0
alias nouveau off
alias lbm-nouveau off
EOF

    # Configure X.org
    mkdir -p /etc/X11/xorg.conf.d/
    cat > /etc/X11/xorg.conf.d/10-nvidia.conf << 'EOF'
Section "ServerLayout"
    Identifier "layout"
    Screen 0 "nvidia"
EndSection

Section "Device"
    Identifier "nvidia"
    Driver "nvidia"
    Option "NoLogo" "true"
    Option "UseEDID" "true"
    Option "AllowEmptyInitialConfiguration" "true"
EndSection

Section "Screen"
    Identifier "nvidia"
    Device "nvidia"
    Option "AllowEmptyInitialConfiguration" "true"
EndSection

Section "Module"
    Load "modesetting"
    Load "glx"
EndSection
EOF

    # Create display setup script
    cat > /usr/local/bin/setup-display << 'EOF'
#!/bin/bash

# Remove nouveau if loaded
rmmod nouveau || true

# Load NVIDIA kernel modules
modprobe nvidia
modprobe nvidia_drm
modprobe nvidia_uvm
modprobe nvidia_modeset

# Wait for NVIDIA devices
sleep 2

# Configure displays
xrandr --auto
if ! xrandr | grep -q "connected"; then
    xrandr --setprovideroutputsource modesetting NVIDIA-0
    xrandr --auto
fi
EOF
    chmod +x /usr/local/bin/setup-display

    # Update initramfs
    update-initramfs -u -k all

    # Create systemd service for NVIDIA setup
    cat > /etc/systemd/system/nvidia-setup.service << 'EOF'
[Unit]
Description=NVIDIA display setup
Before=display-manager.service
After=systemd-modules-load.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup-display
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    # Enable the service
    systemctl enable nvidia-setup

    # Create X11 startup hook
    mkdir -p /etc/X11/xinit/xinitrc.d
    cat > /etc/X11/xinit/xinitrc.d/10-nvidia.sh << 'EOF'
#!/bin/bash
if [ -x /usr/local/bin/setup-display ]; then
    /usr/local/bin/setup-display
fi
EOF
    chmod +x /etc/X11/xinit/xinitrc.d/10-nvidia.sh

    # Configure GDM to use X11
    if [ -f /etc/gdm3/daemon.conf ]; then
        sed -i 's/#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/daemon.conf
    fi
}

# Add kernel modules to load at boot
add_nvidia_modules() {
    cat > /etc/modules-load.d/nvidia.conf << 'EOF'
nvidia
nvidia_drm
nvidia_uvm
nvidia_modeset
EOF
}

# Run setup
setup_nvidia
add_nvidia_modules

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
