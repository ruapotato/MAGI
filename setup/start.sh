#!/bin/bash

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create log directories and context file
mkdir -p "$HOME/.cache/magi/logs"
mkdir -p "$HOME/.cache/magi/crash_reports"
mkdir -p "/tmp/MAGI"
touch "/tmp/MAGI/current_context.txt"
chmod 666 "/tmp/MAGI/current_context.txt"

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

# Function to start MAGI shell with crash handling
start_magi_shell() {
    local crash_count=0
    local last_crash_time=0
    local crash_log_file="$HOME/.cache/magi/crash_reports/magi_shell_crash_$(date +%Y%m%d_%H%M%S).log"
    
    while true; do
        current_time=$(date +%s)
        
        # Reset crash counter if last crash was more than 5 minutes ago
        if [ $((current_time - last_crash_time)) -gt 300 ]; then
            crash_count=0
        fi
        
        # Check if we've had too many crashes
        if [ $crash_count -ge 5 ]; then
            echo "Too many crashes in short period. Waiting 5 minutes before trying again..." >> "$crash_log_file"
            sleep 300
            crash_count=0
        fi
        
        # Start MAGI shell with crash logging
        echo "Starting MAGI shell at $(date)" >> "$crash_log_file"
        {
            python3 "$SCRIPT_DIR/magi_shell.py" 2>&1 
        } >> "$crash_log_file" 2>&1
        
        exit_code=$?
        crash_time=$(date +%s)
        
        # Log crash information
        echo "MAGI shell exited with code $exit_code at $(date)" >> "$crash_log_file"
        echo "Stack trace (if available):" >> "$crash_log_file"
        if [ -f /var/log/syslog ]; then
            grep -A 10 "python3.*magi_shell\.py" /var/log/syslog | tail -n 10 >> "$crash_log_file"
        fi
        
        # Update crash statistics
        last_crash_time=$crash_time
        ((crash_count++))
        
        # If normal exit (0), break the loop
        if [ $exit_code -eq 0 ]; then
            echo "MAGI shell exited normally" >> "$crash_log_file"
            break
        fi
        
        echo "MAGI shell crashed. Restarting in 3 seconds..." >> "$crash_log_file"
        sleep 3
    done
}

# Function to start model manager
start_model_manager() {
    local log_file="$HOME/.cache/magi/logs/model_manager.log"
    echo "Starting Model Manager at $(date)" >> "$log_file"
    python3 "$SCRIPT_DIR/model_manager.py" 2>&1 >> "$log_file" &
}

# Ensure DBUS is running first
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS
fi

# Wait for DBUS to be fully ready
sleep 1

# Start system services in order
/usr/lib/at-spi2-core/at-spi-bus-launcher --launch-immediately &
sleep 1

# Initialize XRandR
xrandr --auto

# Configure settings daemon plugins
export GSETTINGS_BACKEND=dconf
gsettings set org.mate.SettingsDaemon.plugins.xrandr active true
gsettings set org.mate.SettingsDaemon.plugins.xsettings active true
gsettings set org.mate.SettingsDaemon.plugins.keyboard active true
gsettings set org.mate.SettingsDaemon.plugins.media-keys active true
gsettings set org.mate.SettingsDaemon.plugins.mouse active true
gsettings set org.mate.SettingsDaemon.plugins.background active true

# Start settings daemon with monitoring
SETTINGS_DAEMON_LOG="$HOME/.cache/magi/logs/mate-settings-daemon.log"
if [ -x /usr/lib/mate-settings-daemon/mate-settings-daemon ]; then
    mate-settings-daemon --replace --debug > "$SETTINGS_DAEMON_LOG" 2>&1 &
    
    # Wait for settings daemon to initialize
    for i in {1..30}; do
        if pgrep mate-settings-daemon >/dev/null; then
            break
        fi
        sleep 0.1
    done
    
    # Verify and retry if needed
    if ! pgrep mate-settings-daemon >/dev/null; then
        echo "Warning: mate-settings-daemon failed to start, retrying..." >> "$SETTINGS_DAEMON_LOG"
        mate-settings-daemon --replace --debug >> "$SETTINGS_DAEMON_LOG" 2>&1 &
        sleep 2
    fi
fi

# Authentication agent setup
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

# Create default config if it doesn't exist
mkdir -p "$HOME/.config/magi"
CONFIG_FILE="$HOME/.config/magi/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << EOF
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
fi

# Start GVFS
/usr/lib/gvfs/gvfsd &
/usr/lib/gvfs/gvfsd-fuse "$XDG_RUNTIME_DIR/gvfs" &

# Wait for X11 to be ready
for i in {1..30}; do
    if xset q &>/dev/null; then
        break
    fi
    sleep 0.1
done

# Ensure window manager is running first
if ! pgrep marco >/dev/null; then
    marco --replace &
    sleep 2
fi

# Start compositing
xcompmgr -c &

# Start MATE Power Manager
mate-power-manager &

# Load config values
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

# Start model manager (this will handle Ollama and Whisper)
echo "Starting Model Manager..."
start_model_manager

# Start MAGI shell with crash handling
start_magi_shell &

# Wait for shell to start
sleep 3

# Bug workaround: Restart settings daemon after shell starts
mate-settings-daemon --replace
