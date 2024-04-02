#!/bin/bash

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <csvs dir>"
    exit 1
fi

input_csvs=$1

nbr_csvs=$(ls ${input_csvs}/*.csv | wc -l)

echo "Found ${nbr_csvs} csvs"
ls ${input_csvs}/*.csv
read -p "Do you want to start the runs? (y/n) " -n 1 -r
echo
if [[ ${REPLY} =~ ^[Yy]$ ]]; then
    for csv in ${input_csvs}/*.csv; do
        /fs2/sw/bnf-scripts/start_nextflow_analysis.pl ${csv}
        sleep 5
    done
fi
