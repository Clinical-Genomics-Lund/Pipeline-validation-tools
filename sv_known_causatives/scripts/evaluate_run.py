#!/usr/bin/env python3

import argparse
import subprocess
import pathlib
import shutil


def main():
    args = parse_arguments()

    # FIXME: Only needed when actually going to run it?
    if not check_svdb():
        print('"svdb" needs to be available in the PATH variable')
        print("If running on a cluster, you can run it as such:")
        print("singularity run -B <drive> <container> bash evaluate_run.sh <input csv> <outdir dir>")
        raise ValueError("SVDB must be present in PATH")

    print(f"Running SVDB with bnd_distance {args.bnd_distance} and overlap {args.overlap}")
    print(f"Will write output to {args.outdir}")

    outdir_path = pathlib.Path(args.outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    first_line = True
    with open(args.csv) as in_fh:
        for line in in_fh:
            if first_line:
                first_line = False
                continue
        
        line = line.rstrip()
        fields = line.split(",")
        label = fields[0]
        result = fields[1]
        baseline = fields[2]

        print(f"Looking for matches in {label}")
        out_fp = f"{args.outdir}/{label}.query_out.vcf"

        write_baseline()

        # Check if .match exists
        # If so, skip
        # else
        run_svdb(args.bnd_distance, args.overlap, baseline, result)


    print_summary()

def check_svdb() -> bool:
    command = 'svdb'
    return shutil.which(command) is not None


def write_baseline():
    pass


def run_svdb(bnd_distance: int, overlap: float, baseline: str, query_vcf: str):
    pass
    # svdb \
    # --query \
    # --bnd_distance ${bnd_distance} \
    # --overlap ${overlap} \
    # --db ${baseline} \
    # --query_vcf ${result} \
    # --out_occ MATCH | grep -v "^#" | grep "MATCH" > "${out_fp}.match"


def print_summary():
    headers = ['label', 'type', 'chr', 'pos', 'len', 'type', 'callers', 'rank_result', 'rank_score']




def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--csv", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--bnd_distance", default=25000)
    parser.add_argument("--overlap", default=0.7)

    args = parser.parse_args()
    return args



if __name__ == "__main__":
    main()
