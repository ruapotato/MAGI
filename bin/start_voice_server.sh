#!/bin/bash

# Get the root directory (parent of bin)
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

# Source Python environment if needed
if [ -f "${ROOT_DIR}/voice_pyenv/bin/activate" ]; then
    source "${ROOT_DIR}/voice_pyenv/bin/activate"
fi

# Set up PYTHONPATH
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH}"

# Start the voice server
python3 "${ROOT_DIR}/src/utils/voice.py"
