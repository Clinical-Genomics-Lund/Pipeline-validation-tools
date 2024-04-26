#!/bin/bash

if [[ $# -ne 2 && $# -ne 4 ]]; then
    echo "Usage: $0 <base dir> <results1 prefix> [<results2 base dir>] [<results2 prefix>]"
    exit 1
fi

base=$1
prefix=$2
res2_base=$3
res2_prefix=$4

wc -l "${base}/yaml/${prefix}.yaml"

[[ ! -z ${res2_base} ]] && wc -l "${res2_base}/yaml/${res2_prefix}.yaml"