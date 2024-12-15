#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get absolute path to project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
USERNAME=$(whoami)

echo -e "${BLUE}Setting up MAGI Shell...${NC}"

# Install system dependencies
DEPS=(
    python3-gi
    python3-gi-cairo
    python3-xlib
    gir1.2-gtk-3.0
    gir1.2-wnck-3.0
    alacritty
    rofi
    feh
    xcompmgr
    adwaita-icon-theme
    libcairo2-dev
    libpango1.0-dev
    mate-desktop-environment-core
    policykit-1-gnome
    mate-polkit
    dbus-x11
    at-spi2-core
    python3-venv
    python3-pip
    python3-dev
    xdotool
    espeak
    libgirepository1.0-dev
    pkg-config
    libportaudio2
    portaudio19-dev
)

echo -e "${BLUE}Checking dependencies...${NC}"
MISSING_DEPS=()

for dep in "${DEPS[@]}"; do
    if ! dpkg-query -W -f='${Status}' "$dep" 2>/dev/null | grep -q "install ok installed"; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo -e "${RED}Missing dependencies:${NC} ${MISSING_DEPS[*]}"
    echo -e "${BLUE}Installing missing dependencies...${NC}"
    if sudo apt-get update && sudo apt-get install -y "${MISSING_DEPS[@]}"; then
        echo -e "${GREEN}Dependencies installed successfully${NC}"
    else
        echo -e "${RED}Failed to install dependencies${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}All dependencies are installed${NC}"
fi


# Create Python virtual environment for voice server
echo -e "${BLUE}Creating Python virtual environment for voice server...${NC}"
VENV_DIR="$SCRIPT_DIR/voice_pyenv"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    pip install --upgrade pip
    pip install "TTS==0.22.0" --no-deps
    pip install numpy scipy torch torchaudio
    pip install "transformers<4.30.0" "tokenizers<0.14.0"
    pip install librosa scikit-learn inflect
    pip install "TTS==0.21.1"
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
    
    pip install watchdog
    
    pip install python-prctl
    
    pip install sounddevice

    deactivate
    
    echo -e "${GREEN}Virtual environment created and dependencies installed${NC}"
else
    echo -e "${BLUE}Virtual environment already exists${NC}"
fi


# Create start script for Whisper server
cat > "$SCRIPT_DIR/start_voice_server.sh" << 'EOL'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/voice_pyenv/bin/activate"
python "$SCRIPT_DIR/voice.py"
EOL
chmod +x "$SCRIPT_DIR/start_voice_server.sh"

# Create Python virtual environment for the Whisper server
echo -e "${BLUE}Creating Python virtual environment for Whisper server...${NC}"
VENV_DIR="$SCRIPT_DIR/ears_pyenv"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Install server dependencies
    echo -e "${BLUE}Installing Python packages...${NC}"
    pip install --upgrade pip
    
    # Install CUDA support
    echo -e "${BLUE}Installing CUDA support via pip...${NC}"
    pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu118
    
    # Install other dependencies
    pip install transformers
    pip install flask
    pip install numpy
    pip install sounddevice
    pip install requests
    pip install nvidia-ml-py
    pip install psutil
    pip install accelerate>=0.26.0
    
    deactivate
    
    echo -e "${GREEN}Virtual environment created and dependencies installed${NC}"
else
    echo -e "${BLUE}Virtual environment already exists${NC}"
fi

# Make scripts executable
chmod +x "$SCRIPT_DIR/magi_shell.py"
chmod +x "$SCRIPT_DIR/start.sh"

# Create necessary directories
mkdir -p ~/.config/magi
mkdir -p ~/.local/share/applications

# Create MAGI config directory
mkdir -p ~/.config/magi
cat > ~/.config/magi/config.json << EOL
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
EOL

# Create start script for Whisper server
cat > "$SCRIPT_DIR/start_whisper_server.sh" << 'EOL'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/ears_pyenv/bin/activate"
python "$SCRIPT_DIR/server.py"
EOL

chmod +x "$SCRIPT_DIR/start_whisper_server.sh"

# Create systemd service file for Whisper server
sudo tee /etc/systemd/system/magi-whisper.service << EOL
[Unit]
Description=MAGI Whisper Speech Recognition Server
After=network.target

[Service]
Type=simple
User=$USERNAME
ExecStart=$SCRIPT_DIR/start_whisper_server.sh
WorkingDirectory=$SCRIPT_DIR
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOL

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable magi-whisper.service
sudo systemctl start magi-whisper.service

# Create desktop entry
sudo mkdir -p /usr/share/xsessions
sudo tee /usr/share/xsessions/magi.desktop << EOL
[Desktop Entry]
Name=MAGI Shell
Comment=Machine Augmented GTK Interface
Exec=${SCRIPT_DIR}/start.sh
Type=Application
DesktopNames=MAGI
EOL

# Create application launcher entry
cat > ~/.local/share/applications/magi.desktop << EOL
[Desktop Entry]
Name=MAGI Shell
Comment=Machine Augmented GTK Interface
Exec=${SCRIPT_DIR}/start.sh
Type=Application
Categories=System;
Icon=preferences-desktop
EOL

# Add environment variables to .profile
if ! grep -q "MAGI_DIR" "$HOME/.profile" 2>/dev/null; then
    cat >> "$HOME/.profile" << EOL

# MAGI Shell environment
export MAGI_DIR="${SCRIPT_DIR}"
export GTK_THEME=Adwaita
export XCURSOR_THEME=Adwaita
export XCURSOR_SIZE=24
EOL
fi

# Create custom background directory and copy default background
sudo mkdir -p /usr/share/magi/backgrounds
sudo cp /usr/share/backgrounds/mate/desktop/Ubuntu-Mate-Cold-no-logo.png /usr/share/magi/backgrounds/default.png

# Create session file
sudo mkdir -p /usr/share/magi
sudo tee /usr/share/magi/session.conf << EOL
export XDG_CURRENT_DESKTOP=MAGI
export GTK_THEME=Adwaita
export XCURSOR_THEME=Adwaita
export XCURSOR_SIZE=24
export DISPLAY=:0
EOL

# Verify installation
echo -e "\n${GREEN}MAGI Shell setup complete!${NC}"
echo -e "${BLUE}Installation details:${NC}"
echo -e "Project location: ${NC}$SCRIPT_DIR"
echo -e "Configuration: ${NC}~/.config/magi/config.json"
echo -e "Session entry: ${NC}/usr/share/xsessions/magi.desktop"
echo -e "Application entry: ${NC}~/.local/share/applications/magi.desktop"
echo -e "Whisper server: ${NC}systemctl status magi-whisper.service"

# Print usage instructions
echo -e "\n${BLUE}Usage instructions:${NC}"
echo "1. Log out of your current session"
echo "2. Select 'MAGI Shell' from your display manager's session list"
echo "3. Log in to start MAGI"

# Basic keybindings
echo -e "\n${BLUE}Default shortcuts:${NC}"
echo "Alt + Space: Launch application menu"
echo "Alt + Tab: Switch windows"
echo "Ctrl + Alt + T: Launch terminal"
echo "Alt + F4: Close window"

# Clean up any existing instances
pkill -f magi_shell.py >/dev/null 2>&1
pkill xcompmgr >/dev/null 2>&1

# Offer to test the setup
echo -e "\n${BLUE}Would you like to test MAGI Shell now? (y/n)${NC}"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo "Starting MAGI Shell..."
    exec "$SCRIPT_DIR/start.sh"
fi
