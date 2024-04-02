#!/bin/bash

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input csvs> <eval csv>"
    exit 1
fi

input_csvs=$1
eval_csv=$2

