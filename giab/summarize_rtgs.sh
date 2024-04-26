#!/bin/bash

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <... rtg dirs>"
    exit 1
fi

cat $1/summary.txt | head -2

for file in "$@"; do
    printf "$(cat ${file}/summary.txt | tail -1)\t${file}\n"
done
