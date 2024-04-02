#!/bin/bash

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <input csvs> <run base> <main.nf> <work base>"
    exit 1
fi

input_csvs=$1
run_base=$2
main=$3
work_base=$4

echo "Input csvs: ${input_csvs}"
echo "Run base: ${run_base}"

mkdir -p ${run_base}

nbr_csvs=$(ls ${input_csvs}/*.csv | wc -l)

sbatch_template() {
    local jobname="$1"
    local main="$2"
    local profile="$3"
    local workdir="$4"
    local trace="$5"
    local in_csv="$6"
    local outdir="$7"

    cat <<- EOF
#!/bin/bash
#SBATCH --job-name=${jobname}
#SBATCH --output=slurm_logs/%j.log
#SBATCH --ntasks=4
#SBATCH --mem=4gb
#SBATCH --time=7-00:00:00
       
module load Java/13.0.2
module load nextflow/23.04.2
module load singularity/3.2.0
        
export NXF_OFFLINE=TRUE

nextflow run ${main} \\
    -profile ${profile} \\
    -resume \\
    -w ${workdir} \\
    --outdir ${outdir}_${SLURM_JOB_ID} \\
    --input ${in_csv}
EOF
}

echo "Found ${nbr_csvs} csvs"
read -p "Do you want to start the run? (y/n) " -n 1 -r
echo
if [[ ${REPLY} =~ ^[Yy]$ ]]; then
    for csv in ${input_csvs}/*.csv; do
        label=$(echo ${csv%.csv} | sed "s|.*/||")
        echo "${csv} (label ${label})"
        run_sample="${run_base}/${label}"
        mkdir -p ${run_sample}
        
        work_sample="${work_base}/${label}"
        mkdir -p "${work_sample}"

        outdir="${run_sample}/output"
        mkdir -p ${outdir}
        mkdir -p "${run_sample}/slurm_logs"
        trace="${run_sample}/trace.txt"

        csv_abs=$(realpath "${csv}")

        sbatch_sample="${run_sample}/run.run"
        echo "$(sbatch_template "rd_sveval_${label}" "${main}" cmd "${work_sample}" "${trace}" "${csv_abs}" "${outdir}")" > ${sbatch_sample}

    done
fi

nbr_runfiles=$(ls ${run_base}/*/run.run | wc -l)
echo "Found ${nbr_runfiles} run files"
read -p "Do you want to start the runs? (y/n) " -n 1 -r
echo
if [[ ${REPLY} =~ ^[Yy]$ ]]; then
    for runfile in ${run_base}/*/run.run; do
        cd "$(dirname "${runfile}")"
        echo "Starting run: ${runfile}"
        sbatch run.run
        cd -
        sleep 5
    done
fi










