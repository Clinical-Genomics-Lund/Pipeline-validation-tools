#!/bin/bash

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <input csv> <output dir>"
    exit 1
fi

if ! command -v svdb >/dev/null 2>&1; then
    echo '"svdb" needs to be available in the PATH variable'
    echo "If running on a cluster, you can run it as such:"
    echo "singularity run -B <drive> <container> bash evaluate_run.sh <input csv> <outdir dir>"
    exit 1
fi

input_csv=$1
output_dir=$2

bnd_distance=25000
overlap=0.7

echo "Running SVDB with bnd_distance ${bnd_distance} and overlap ${overlap}"

echo "Will write output to ${output_dir}"
mkdir -p "${output_dir}"

tail -n +2 ${input_csv} | while read line; do

    label=$(echo ${line} | cut -f1 -d",")
    result=$(echo ${line} | cut -f2 -d",")
    baseline=$(echo ${line} | cut -f3 -d",")

    echo "Looking for matches in ${label}"
    out_fp="${output_dir}/${label}.query_out.vcf"
    grep -v "^#" ${baseline} > "${out_fp}.baseline"

    if [[ -f "${out_fp}.match" ]]; then
        echo "${out_fp}.match already exists, skipping"
    else
        svdb \
            --query \
            --bnd_distance ${bnd_distance} \
            --overlap ${overlap} \
            --db ${baseline} \
            --query_vcf ${result} \
            --out_occ MATCH | grep -v "^#" | grep "MATCH" > "${out_fp}.match"
    fi
done

function concatenate() {
    tr "\n" "," | sed "s/,$//"
}

function getinfo() {
    sed "s/.*${1}=//" | sed "s/;.*//"
}

echo -e "label\ttype\tchr\tpos\tlen\ttype\tcallers"
for out in ${output_dir}/*.match; do

    label=$(echo ${out} | sed "s|.*/||" | sed "s|\..*||")
    match_nbr_lines=$(wc -l ${out} | cut -f1 -d" ")
    baseline="${out%.match}.baseline"
    base_nbr_lines=$(wc -l ${baseline} | cut -f1 -d" ")

    if [[ ${base_nbr_lines} -eq 1 ]]; then
        base_chr=$(cut -f1 ${baseline})
        base_pos=$(cut -f2 ${baseline})
        base_len=$(cut -f8 ${baseline} | getinfo "SVLEN")
        base_type=$(cut -f5 ${baseline} | tr -d "<" | tr -d ">")
        base_caller=$(cut -f8 ${baseline} | getinfo "set")
        base_rank_result=$(cut -f8 ${baseline} | getinfo "RankResult")
        base_rank_score=$(cut -f8 ${baseline} | getinfo "RankScore")
    elif [[ "${base_nbr_lines}" -eq 1 ]]; then
        base_chr="-"
        base_pos="-"
        base_len="-"
        base_type="-"
        base_caller="-"
        base_rank_result="-"
        base_rank_score="-"
    else 
        base_chr=$(cut -f1 ${baseline} | concatenate)
        base_pos=$(cut -f2 ${baseline} | concatenate)
        base_len=$(cut -f8 ${baseline} | getinfo "SVLEN" | concatenate)
        base_type=$(cut -f5 ${baseline} | tr -d "<" | tr -d ">" | concatenate)
        base_caller=$(cut -f8 ${baseline} | getinfo "set" | concatenate)
        base_rank_result=$(cut -f8 ${baseline} | getinfo "RankResult" | concatenate)
        base_rank_score=$(cut -f8 ${baseline} | getinfo "RankScore" | concatenate)
    fi

    if [[ "${match_nbr_lines}" -eq 1 ]]; then
        chr=$(cut -f1 ${out})
        pos=$(cut -f2 ${out})
        len=$(cut -f8 ${out} | getinfo "SVLEN")
        type=$(cut -f5 ${out} | tr -d "<" | tr -d ">")
        caller=$(cut -f8 ${out} | getinfo "set")
        rank_result=$(cut -f8 ${baseline} | getinfo "RankResult")
        rank_score=$(cut -f8 ${baseline} | getinfo "RankScore")
    elif [[ "${match_nbr_lines}" -eq 0 ]]; then
        chr="-"
        pos="-"
        len="-"
        type="-"
        caller="-"
        rank_result="-"
        rank_score="-"
    else
        chr=$(cut -f1 ${out} | concatenate)
        pos=$(cut -f2 ${out} | concatenate)
        len=$(cut -f8 ${out} | getinfo "SVLEN" | concatenate)
        type=$(cut -f5 ${out} | tr -d "<" | tr -d ">" | concatenate)
        caller=$(cut -f8 ${out} | getinfo "set" | concatenate)
        rank_result=$(cut -f8 ${baseline} | getinfo "RankResult" | concatenate)
        rank_score=$(cut -f8 ${baseline} | getinfo "RankScore" | concatenate)
    fi
    echo -e "${label}\tbase\t${base_chr}\t${base_pos}\t${base_len}\t${base_type}\t${base_caller}\t${base_rank_result}\t${base_rank_score}"
    echo -e "${label}\trun\t${chr}\t${pos}\t${len}\t${type}\t${caller}\t${rank_result}\t${rank_score}"
done | cut -c1-10000
# cut -c1-1000 to prevent CSQ flooding terminal with enormous lines













