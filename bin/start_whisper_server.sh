#!/bin/bash
SCRIPT_DIR="/home/david/MAGI"
source "$SCRIPT_DIR/ears_pyenv/bin/activate"
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
python "$SCRIPT_DIR/src/utils/whisper_server.py"
