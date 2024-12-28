#!/bin/bash
# Activate virtualenv
source "/home/david/MAGI/ears_pyenv/bin/activate"
# Set proper Python path
export PYTHONPATH="/home/david/MAGI/ears_pyenv/lib/python3.11/site-packages"
# Start the server
exec python3 "/home/david/MAGI/whisper_server.py"
