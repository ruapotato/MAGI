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
    espeak \
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
    python3-numpy \
    xterm \
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
    feh \
    xcompmgr \
    rofi \
    alacritty \
    network-manager \
    network-manager-gnome \
    pulseaudio \
    pavucontrol \
    xclip \
    wmctrl\
    curl \
    adwaita-icon-theme \
    python3-requests \
    python3-gi \
    python3-gi-cairo \
    python3-prctl \
    python3-watchdog \
    python3-soundfile \
    python3-torch \
    python3-psutil \
    python3-pynvml \
    gir1.2-gtk-4.0 \
    libadwaita-1-0 \
    gir1.2-adw-1 \
    gir1.2-vte-2.91 \
    gir1.2-vte-3.91 \
    python3-pyaudio \
    python3-scipy \
    libsndfile1 \
    ffmpeg \
    libcap-dev
    

# Create required MAGI directories
mkdir -p /tmp/MAGI
touch /tmp/MAGI/current_context.txt
chmod 777 /tmp/MAGI/current_context.txt

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
AutomaticLoginEnable=true
AutomaticLogin=magi
InitialSetupEnable=false
GDM

# Create X11 startup script
mkdir -p /etc/X11/xinit/xinitrc.d
cat > /etc/X11/xinit/xinitrc.d/50-magi-startup << 'EOF'
#!/bin/bash
if ! pgrep gdm3 > /dev/null; then
    sudo service gdm3 start
fi

if ! pgrep gdm3 > /dev/null; then
    exec /opt/magi/start.sh
fi
EOF
chmod +x /etc/X11/xinit/xinitrc.d/50-magi-startup

# Set up Python environment for voice
python3 -m venv /opt/magi/voice_pyenv
source /opt/magi/voice_pyenv/bin/activate
pip install --upgrade pip
pip install "TTS==0.22.0" --no-deps
pip install numpy scipy torch torchaudio
pip install "transformers<4.30.0" "tokenizers<0.14.0"
pip install librosa scikit-learn inflect
# Core processing libraries
pip install einops encodec flask pandas matplotlib

# Text processing libraries
pip install anyascii nltk unidecode num2words pysbd cython coqpit aiohttp

# Language-specific packages
pip install jieba pypinyin
pip install bangla bnnumerizer bnunicodenormalizer
pip install g2pkk hangul-romanize jamo

# Install spacy with Japanese support
pip install "spacy[ja]>=3"

# Install additional required packages
pip install gruut[de,es,fr]==2.2.3
pip install umap-learn trainer>=0.0.32

# Update transformers to required version
pip install --upgrade "transformers>=4.33.0"

# Fix pandas version
pip install "pandas>=1.4,<2.0"

# more dependencies
pip install watchdog
pip install python-prctl
pip install sounddevice
    
# 🎭 The Grand Voice Model Summoning Ceremony 🎭
cat > /opt/magi/summon_the_voice.py << 'DRAMATIC_FINALE'
#!/usr/bin/env python3
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Optional, Tuple, Literal
import torch
from TTS.api import TTS
import shutil

VocalPerformers = Literal[
    "p226",  # The Mysterious Baritone
    "p326",  # The Dramatic Bass
    "p330",  # The Smooth Operator
    "p347"   # The Gentle Giant
]

@dataclass
class TheatricalVoiceSummoner:
    backstage_preparation: Optional[TTS] = None
    green_room: Path = Path('/opt/magi/voice_models')
    chosen_performer: str = "tts_models/en/vctk/vits"
    
    def prepare_for_opening_night(self) -> Tuple[bool, str]:
        """🎭 The stage is set, the curtains drawn..."""
        try:
            # Preparing the stage
            self.green_room.mkdir(parents=True, exist_ok=True)
            
            # Summoning our star performer
            print("🎭 Casting the leading role...")
            self.backstage_preparation = TTS(
                model_name=self.chosen_performer,
                progress_bar=False
            ).to("cuda" if torch.cuda.is_available() else "cpu")
            
            # Instead of using save_pretrained, we'll copy the downloaded model
            print("📜 Memorizing the script...")
            model_path = Path.home() / ".local/share/tts/tts_models--en--vctk--vits"
            if model_path.exists():
                # Copy all files from the downloaded model directory
                for file in model_path.glob('*'):
                    shutil.copy2(file, self.green_room / file.name)
                return True, "Standing ovation! The voice model has taken the stage! 🎊"
            else:
                return False, "The performer seems to have missed their cue! Model not found. 😱"
            
        except Exception as stage_fright:
            return False, f"Performance anxiety struck: {stage_fright} 😱"

def orchestrate_the_performance() -> int:
    """🎬 Ladies and gentlemen, the show is about to begin!"""
    print("🎭 Welcome to tonight's performance of The Voice Model! 🎭")
    
    director = TheatricalVoiceSummoner()
    show_must_go_on, critics_review = director.prepare_for_opening_night()
    
    print(critics_review)
    return 0 if show_must_go_on else 1

if __name__ == "__main__":
    sys.exit(orchestrate_the_performance())
DRAMATIC_FINALE

# 🎬 And now, for our feature presentation...
chmod +x /opt/magi/summon_the_voice.py

echo "🎭 Raising the curtain on our voice model performance..."
python3 /opt/magi/summon_the_voice.py

# Taking a bow
echo "🎭 The voice model installation has concluded! *bows gracefully* 🎭"
# The Great Espeak Masquerade
if ln -s /opt/magi/magi_espeak.py /usr/bin/magi_espeak; then
    echo "🎭 Behold! Our python script is now masterfully disguised as espeak!"
else
    echo "😱 Alas! Our cunning plan of impersonation has been foiled!"
    exit 1
fi
    
deactivate


# Set up Python environment ears
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
    psutil \
    sounddevice \
    TTS

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

# Pull Mistral model in a controlled way
(
    echo "Starting Ollama service temporarily..."
    /usr/local/bin/ollama serve &
    OLLAMA_PID=$!
    
    # Wait for service to be ready
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    echo "Pulling Mistral model..."
    /usr/local/bin/ollama pull mistral
    
    echo "Stopping temporary Ollama service..."
    kill $OLLAMA_PID
    wait $OLLAMA_PID 2>/dev/null || true
    
    # Make sure no Ollama processes are left
    pkill -f ollama || true
    sleep 1
    pkill -9 -f ollama || true
) || true

# Clean up any remaining Ollama processes to be absolutely certain
pkill -f ollama || true
sleep 1
pkill -9 -f ollama || true

# Create desktop entry
cat > /usr/share/xsessions/magi.desktop << 'DESKTOP'
[Desktop Entry]
Name=MAGI Shell
Comment=Machine Augmented GTK Interface
Exec=/opt/magi/start.sh
Type=Application
DesktopNames=MAGI
DESKTOP

# Create MAGI systemd service
cat > /etc/systemd/system/magi-session.service << 'EOF'
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

# Configure TTY autologin
mkdir -p /etc/systemd/system/getty@tty{1,2,3,4,5,6}.service.d/
for i in {1..6}; do
    cat > "/etc/systemd/system/getty@tty${i}.service.d/override.conf" << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin magi --noclear %I \$TERM
Type=idle
EOF
done

# Create magi user if it doesn't exist
if ! id -u magi >/dev/null 2>&1; then
    useradd -m -s /bin/bash magi
    echo "magi:magi" | chpasswd
    usermod -aG sudo magi
fi

# Set up proper permissions
chown -R magi:magi /opt/magi
chmod -R 755 /opt/magi

# Enable services
systemctl enable gdm3
systemctl enable NetworkManager
systemctl enable ollama
systemctl enable magi-whisper
systemctl enable magi-session

# Clean up
apt-get clean
