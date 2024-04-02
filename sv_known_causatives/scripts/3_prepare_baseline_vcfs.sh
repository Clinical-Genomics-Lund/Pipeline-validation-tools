#!/bin/bash

if [[ $# -ne 2 ]]; then
    echo "Usage: ${0} <summary table> <output dir>"
    exit 1
fi

summary_table=$1
out_dir=$2

cat ${summary_table} | cut -f1 -d"," | tail -n +2 | uniq | while read sample_id; do
    echo "Processing ${sample_id}"
    # The label is the file name without suffix
    label=$(echo ${path%.vcf.gz} | sed "s|.*/||")
    grep "^#" "${path}" > "${out_dir}/${label}.vcf"

    cat ${summary_table} | grep ${sample_id} | while read line; do
        path=$(echo ${line} | cut -f5)
        variant_pos=$(echo ${line} | cut -f2,3)
        # FIXME: We need a for loop here as well, to handle multiple variants
        tabix "${path}" "${variant_pos}" | grep "${type}" | head -1 >> "${out_dir}/${label}.vcf"
    done

done



