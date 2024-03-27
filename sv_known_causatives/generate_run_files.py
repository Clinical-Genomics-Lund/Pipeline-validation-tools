#!/usr/bin/env python3

import argparse
import os

__version_info__ = ("1", "0", "0")
__version__ = ".".join(__version_info__)


def main():
    args = parse_arguments()

    os.makedirs(args.outdir, exist_ok=True)

    csv_paths = list()
    for csv in os.listdir(args.input_csvs):
        csv_paths.append(csv)
        if csv.endswith(".csv"):
            
            base_name = csv.rstrip(".csv")
            workdir = f"{args.work_base}/{base_name}"
            outdir = f"{args.outdir}/{base_name}"
            sbatch_file = get_sbatch_file(f"{args.input_csvs}/{csv}", args.main_nf, args.profile, workdir, outdir)
            with open(f"{args.outdir}/{base_name}.run", 'w') as out_fh:
                out_fh.write(sbatch_file)
    
    print(f"{len(csv_paths)} CSVs written to {args.outdir}")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s ({__version__})")
    parser.add_argument("--input_csvs", help="Folder containing input CSVs for the runs", required=True)
    parser.add_argument("--outdir", help="Folder to store run files", required=True)
    parser.add_argument("--main_nf", help="Location of the main.nf to execute", required=True)
    parser.add_argument("--profile", help="Profile", required=True)
    parser.add_argument("--work_base", help="Base directory for work directories", required=True)
    args = parser.parse_args()
    return args


def get_sbatch_file(csv: str, main_nf: str, profile: str, workdir: str, outdir: str) -> str:

    job_name = 'testrun'
    template = get_sbatch_template(job_name, main_nf, profile, workdir, csv, outdir)
    return template


def get_sbatch_template(job_name: str, main: str, profile: str, workdir: str, in_csv: str, outdir: str) -> str:

    sbatch_string = f"""
#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output=%j.log
#SBATCH --ntasks=4
#SBATCH --mem=4gb
#SBATCH --time=7-00:00:00
    
module load Java/13.0.2
module load nextflow/23.04.2
module load singularity/3.2.0
        
nextflow run {main} \\
    -profile {profile} \\
    -resume \\
    -w {workdir} \\
    -trace trace.txt \\
    --outdir {outdir}_${{SLURM_JOB_ID}} \\
    --input {in_csv}
    """

    return sbatch_string


if __name__ == '__main__':
    main()
