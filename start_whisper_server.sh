#!/bin/bash

# Activate virtualenv
source /opt/magi/ears_pyenv/bin/activate

# Set proper Python path
export PYTHONPATH=/opt/magi/ears_pyenv/lib/python3.11/site-packages

# Start the server
exec python3 /opt/magi/server.py
