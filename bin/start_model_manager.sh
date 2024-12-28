#!/bin/bash

# Get the root directory (parent of bin)
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

# Add the src directory to PYTHONPATH
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH}"

# Enable debug output
export G_MESSAGES_DEBUG=all

# Start the model manager
python3 -m magi_shell.monitors
