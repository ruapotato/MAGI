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
