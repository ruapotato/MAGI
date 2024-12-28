#!/bin/bash
source "/home/david/MAGI/src/ears_pyenv/bin/activate"
export PYTHONPATH="/home/david/MAGI/src/ears_pyenv/lib/python3.11/site-packages"
exec python3 "/home/david/MAGI/src/whisper_server.py"
