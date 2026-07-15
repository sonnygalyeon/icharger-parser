#!/usr/bin/env sh
set -eu
if [ "$#" -eq 0 ]; then
  echo 'Usage: ./run.sh path/to/log.txt [more logs or folders]'
  exit 2
fi
python3 main.py "$@" -o output
