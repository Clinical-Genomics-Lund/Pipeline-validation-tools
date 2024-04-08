#!/bin/bash

if [[ $# -ne 5 ]]; then
    echo "Usage: rtg_run.sh <rtg path> <sdf path> <benchmark vcf> <calls vcf> <output dir>"
    exit 1
fi

# FIXME: Fix the sensitivity, only work with SNVs within our interval ranges
# FIXME: Why are there no X/Y/(MT)?
# FIXME: Gather all the references
# FIXME: Write up a README

rtg_path=$1
sdf_path=$2
benchmark_vcf=$3
calls_vcf=$4
output=$5

chr_file="${calls_vcf%.vcf.gz}.chr.vcf"

if [[ -f "${chr_file}" ]]; then
    echo "Chr-named file already generated, proceeding with this one: ${chr_file}"
    calls_vcf="${chr_file}.gz"
else if [[ $(zgrep -v "^#" ${calls_vcf} | head -1 | cut -f1) == "1" ]]; then
    echo "Non chr file detected. Generating new file to ${chr_file}.gz"
    zcat  ${calls_vcf} | sed "/^#/! s/^/chr/" > "${chr_file}"
    bgzip ${chr_file}
    calls_vcf="${chr_file}.gz"
fi

if [[ ! -f "${calls_vcf}.tbi" ]]; then
    echo "Generating tabix index"
    tabix ${calls_vcf}
fi

if [[ -d "${output}" ]]; then
    echo "Output folder ${output} already exists. Do you want to remove it? (y/n)"
    read response

    if [[ "${response}" -eq "y" ]]; then
        echo "Removing ${output}"
        rm -r ${output}
    fi
fi

${rtg_path} vcfeval \
    --baseline ${benchmark_vcf} \
    --calls ${calls_vcf} \
    --output ${output} \
    -t ${sdf_path}
