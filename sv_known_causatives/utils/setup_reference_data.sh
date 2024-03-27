#!/bin/bash

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <summary_table> <out_dir>"
    echo "Example using container: singularity run -B /fs1 /fs1/jakob/containers/depot.galaxyproject.org-singularity-tabix-1.11--hdfd78af_0.img bash setup_reference_data.sh sv_validation_samples.csv subsets"
    exit 1
fi

summary_table=$1
out_dir=$2

mkdir -p ${out_dir}

cat "${summary_table}" | tail -n +2 | cut -f1 -d"," | uniq | while read sample_id; do 

    file="${sample_id}_masked.sv.scored.sorted.vcf.gz"
    out_file="${out_dir}/${sample_id}.vcf"
    # echo "${label} ${type} ${chr} ${pos} ${file}"
    # echo "${file}"
    zcat "${file}" | grep "^#" > "${out_file}"

    echo "Processing sample ID ${sample_id}"

    cat "${summary_table}" | tail -n +2 | grep "^${sample_id}" | while read line; do

        type=$(echo "${line}" | cut -f5 -d"," | sed "s|(.*||")
        range=$(echo "${line}" | cut -f6 -d",")
        chr=$(echo "${range}" | cut -f1 -d":")
        pos=$(echo "${range}" | cut -f2 -d":" | cut -f1 -d"-")

        tabix "${file}" "${chr}:${pos}" | grep "${type}" | head -1 >> "${out_file}"
    done
done

