#!/bin/bash

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Ensure basic X11 environment
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

# Kill any existing instances and wait for cleanup
killall -9 mate-settings-daemon 2>/dev/null
killall -9 mate-polkit 2>/dev/null
killall -9 polkit-gnome-authentication-agent-1 2>/dev/null
killall -9 xcompmgr 2>/dev/null
sleep 1

# Essential environment variables
export XAUTHORITY="$HOME/.Xauthority"
export XDG_CURRENT_DESKTOP=MATE:MAGI
export XDG_SESSION_TYPE=x11
export XDG_SESSION_DESKTOP=MAGI
export GTK_THEME=Adwaita
export XCURSOR_THEME=Adwaita
export XCURSOR_SIZE=24

# Set up XDG directories
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_RUNTIME_DIR="/run/user/$UID"

# Start Whisper server if not already running
if ! pgrep -f "python.*server.py" > /dev/null; then
    echo "Starting Whisper server..."
    mkdir -p "$HOME/.cache/magi/logs"
    source "$SCRIPT_DIR/ears_pyenv/bin/activate"
    python "$SCRIPT_DIR/server.py" > "$HOME/.cache/magi/logs/whisper_server.log" 2>&1 &
    deactivate
    
    # Wait for server to start
    for i in {1..30}; do
        if curl -s http://localhost:5000/health >/dev/null 2>&1; then
            echo "Whisper server started successfully"
            break
        fi
        sleep 0.1
    done
fi

# Ensure DBUS is running first
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS
fi

# Wait for DBUS to be fully ready
sleep 1

# Start system services in order
# Start at-spi-bus-launcher for accessibility
/usr/lib/at-spi2-core/at-spi-bus-launcher --launch-immediately &
sleep 1

# Initialize XRandR
xrandr --auto

# Start MATE Settings Daemon with full session support
export GSETTINGS_BACKEND=dconf

# Configure settings daemon plugins before starting
gsettings set org.mate.SettingsDaemon.plugins.xrandr active true
gsettings set org.mate.SettingsDaemon.plugins.xsettings active true
gsettings set org.mate.SettingsDaemon.plugins.keyboard active true
gsettings set org.mate.SettingsDaemon.plugins.media-keys active true
gsettings set org.mate.SettingsDaemon.plugins.mouse active true
gsettings set org.mate.SettingsDaemon.plugins.background active true

# Create log directory if it doesn't exist
mkdir -p "$HOME/.cache/magi/logs"
SETTINGS_DAEMON_LOG="$HOME/.cache/magi/logs/mate-settings-daemon.log"

# Start settings daemon with debug output
if [ -x /usr/lib/mate-settings-daemon/mate-settings-daemon ]; then
    mate-settings-daemon --replace --debug > "$SETTINGS_DAEMON_LOG" 2>&1 &
    
    # Wait for settings daemon to initialize
    for i in {1..30}; do
        if pgrep mate-settings-daemon >/dev/null; then
            break
        fi
        sleep 0.1
    done
    
    # Verify settings daemon is running
    if ! pgrep mate-settings-daemon >/dev/null; then
        echo "Warning: mate-settings-daemon failed to start, check $SETTINGS_DAEMON_LOG"
        # Try one more time
        mate-settings-daemon --replace --debug > "$SETTINGS_DAEMON_LOG" 2>&1 &
        sleep 2
    fi
fi

# Ensure proper polkit and authentication setup
if [ -x /usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1 ]; then
    /usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1 &
elif [ -x /usr/lib/mate-polkit/polkit-mate-authentication-agent-1 ]; then
    /usr/lib/mate-polkit/polkit-mate-authentication-agent-1 &
fi
sleep 2

# Initialize MATE session settings
if [ -x /usr/bin/mate-settings ]; then
    export MATE_DESKTOP_SESSION_ID="this-is-deprecated"
    if [ -f /usr/share/mate/mate-default-settings.ini ]; then
        dconf load / < /usr/share/mate/mate-default-settings.ini
    fi
fi

# Ensure gvfs is running for file operations
/usr/lib/gvfs/gvfsd &
/usr/lib/gvfs/gvfsd-fuse "$XDG_RUNTIME_DIR/gvfs" &

# Wait for X11 to be ready
for i in {1..30}; do
    if xset q &>/dev/null; then
        break
    fi
    sleep 0.1
done

# Start compositing
xcompmgr -c &

# Ensure we have a window manager
if ! pgrep marco >/dev/null; then
    marco --replace &
    sleep 2
fi

# Start MATE Power Manager
mate-power-manager &

# Load specific config values
CONFIG_FILE="$HOME/.config/magi/config.json"
if [ -f "$CONFIG_FILE" ]; then
    while IFS="=" read -r key value; do
        if [ ! -z "$key" ]; then
            export "MAGI_${key}=${value}"
        fi
    done < <(python3 -c '
import json
import sys
try:
    with open("'"$CONFIG_FILE"'") as f:
        config = json.load(f)
    for k, v in config.items():
        print(f"{k.upper()}={v}")
except Exception as e:
    sys.exit(0)
')
fi

# Set background
if [ -f "/usr/share/magi/backgrounds/default.png" ]; then
    feh --bg-fill "/usr/share/magi/backgrounds/default.png" || true
fi

# Start MAGI shell
exec python3 "$SCRIPT_DIR/magi_shell.py" &
# Bug workaround:
sleep 3
mate-settings-daemon --replace
