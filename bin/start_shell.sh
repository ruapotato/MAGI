#!/bin/bash

# Get the root directory (parent of bin)
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

# Add the src directory to PYTHONPATH
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH}"

# Start the MAGI shell
python3 -m magi_shell
