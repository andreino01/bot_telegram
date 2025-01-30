#!/bin/bash
if [[ $(date +%H) -eq 20 ]]; then
  railway up
elif [[ $(date +%H) -eq 3 ]]; then
  railway down
fi
