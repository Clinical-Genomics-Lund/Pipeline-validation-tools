#!/bin/bash

if [[ $# -ne 3 ]]; then
    echo "Usage: generate_samplesheets.sh <template> <fastq folder> <out dir>"
    exit 1
fi

template=$1
base=$2
outdir=$3

mkdir -p ${outdir}

#base="/fs1/jakob/data/sv_validation/spring"

ls ${base}/*.fastq.gz | sed "s/.*\///" | grep R1 | while read f; do
    full_path_fw="${base}/${f}"
    full_path_rv=$(echo "${base}/${f}" | sed "s/R1/R2/")
    label=$(echo ${f} | sed "s/_R1.*//")
    echo "Writing samplesheet to path ${outdir}/${label}.csv"
    cat ${template} | sed "s|<FW>|${full_path_fw}|" | sed "s|<RV>|${full_path_rv}|" > ${outdir}/${label}.csv
done