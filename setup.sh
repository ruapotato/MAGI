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

# Install dependencies
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
    xrandr
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
    "background": "feh --bg-fill /usr/share/magi/backgrounds/default.png"
}
EOL

# Create desktop entry in system-wide location
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
