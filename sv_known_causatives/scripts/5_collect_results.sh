#!/bin/bash

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input csvs> <results csv>"
    exit 1
fi

input_csvs=$1
results_csv=$2

echo "label,result" > ${results_csv}

nbr_csvs=$(ls ${input_csvs}/*.csv | wc -l)

for csv in ${input_csvs}/*.csv; do
    run_name=$(cat ${csv} | tail -1 | cut -f2 -d",")
    path=$(find /fs1/results_dev/wgs/vcf/${run_name} | head -1)
    echo "${run_name},${path}" >> ${results_csv}
done

# Output: label, result, baseline

