#!/bin/bash

if [[ $# -ne 5 && $# -ne 6 ]]; then
    echo "Usage: $0 <rtg path> <sdf path> <bed regions> <benchmark vcf> <calls vcf> <output dir> [<sample>]"
    exit 1
fi

rtg_path=$1
sdf_path=$2
bed_regions=$3
benchmark_vcf=$4
calls_vcf=$5
output=$6
sample=$7

chr_file="${calls_vcf%.vcf.gz}.chr.vcf"

# if [[ -f "${chr_file}.gz" ]]; then
#     echo "Chr-named file already generated, proceeding with this one: ${chr_file}"
#     calls_vcf="${chr_file}.gz"
# el
if [[ $(zgrep -v "^#" ${calls_vcf} | head -1 | cut -f1) == "1" ]]; then
    echo "Non chr file detected. Generating new file to ${chr_file}.gz. Removing X and Y chromosomes."
    zcat  ${calls_vcf} | sed "/^#/! s/^/chr/" | grep -v "^chrX" | grep -v "^chrY" > "${chr_file}"
    bgzip ${chr_file}
    calls_vcf="${chr_file}.gz"

    if [[ -f "${calls_vcf}.tbi" ]]; then
        echo "Removing outdated ${calls_vcf}.tbi"
        rm "${calls_vcf}.tbi"
    fi
fi

if [[ ! -f "${calls_vcf}.tbi" ]]; then
    echo "Generating tabix index"
    tabix ${calls_vcf}
fi

if [[ -d "${output}" ]]; then
    read -p "Output folder ${output} already exists. Do you want to remove it? (y/n) " response

    if [[ "${response}" -eq "y" ]]; then
        echo "Removing ${output}"
        rm -r ${output}
    fi
fi

if [[ -z ${sample} ]]; then
    echo "Executing ${rtg_path} vcfeval --baseline ${benchmark_vcf} --bed-regions ${bed_regions} --calls ${calls_vcf} --output ${output} -t ${sdf_path}"
    ${rtg_path} vcfeval \
        --baseline ${benchmark_vcf} \
        --bed-regions ${bed_regions} \
        --calls ${calls_vcf} \
        --output ${output} \
        -t ${sdf_path}
else
    echo "Executing ${rtg_path} vcfeval --baseline ${benchmark_vcf} --bed-regions ${bed_regions} --calls ${calls_vcf} --output ${output} -t ${sdf_path} --sample ${sample}"
    ${rtg_path} vcfeval \
        --baseline ${benchmark_vcf} \
        --bed-regions ${bed_regions} \
        --calls ${calls_vcf} \
        --output ${output} \
        -t ${sdf_path} \
        --sample ${sample}
fi
