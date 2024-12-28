#!/bin/bash
source "/home/david/MAGI/ears_pyenv/bin/activate"
export PYTHONPATH="/home/david/MAGI/ears_pyenv/lib/python3.11/site-packages:$PYTHONPATH"
exec python3 "/home/david/MAGI/src/utils/whisper_server.py"
