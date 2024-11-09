#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/ears_pyenv/bin/activate"
python "$SCRIPT_DIR/server.py"
