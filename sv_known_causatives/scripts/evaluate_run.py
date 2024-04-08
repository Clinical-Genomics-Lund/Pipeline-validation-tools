#!/usr/bin/env python3

import argparse
import subprocess
import pathlib
import shutil
import io


def main():
    args = parse_arguments()

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
            result_vcf = fields[1]
            baseline_vcf = fields[2]

            print(f"Looking for matches in {label}")
            out_fp = f"{args.outdir}/{label}.query_out.vcf"
            out_baseline_fp = f"{out_fp}.baseline"
            print(f"Writing baseline to {out_baseline_fp}")
            write_baseline(baseline_vcf, out_baseline_fp)

            match_fp = f"{out_baseline_fp}.match"
            match_path = pathlib.Path(match_fp)
            if match_path.exists():
                print(f"{match_path} already exists, skipping (FIXME: Force flag)")
            else:
                run_svdb(args.bnd_distance, args.overlap, baseline_vcf, result_vcf, match_fp)

        # Check if .match exists
        # If so, skip
        # else
        # run_svdb(args.bnd_distance, args.overlap, baseline_vcf, result_vcf)


    print_summary()

def check_svdb() -> bool:
    command = 'svdb'
    return shutil.which(command) is not None


def write_baseline(baseline_vcf_fp: str, out_fp: str):
    with open (baseline_vcf_fp) as in_fh, open(out_fp, 'w') as out_fh:
        for line in in_fh:
            line = line.rstrip()
            if not line.startswith("#"):
                print(line, file=out_fh)



def run_svdb(bnd_distance: int, overlap: float, baseline: str, query_vcf: str, out_fp: str):

    command = [
        "svdb",
        "--query",
        "--bnd_distance",
        f"{bnd_distance}",
        "--overlap",
        f"{overlap}",
        "--db",
        f"{baseline}",
        "--query_vcf",
        f"{query_vcf}",
        "--out_occ",
        "MATCH"
    ]

    print(" ".join(command))

    proc = subprocess.Popen(command, stdout=subprocess.PIPE)

    match_lines = list()
    for line in proc.stdout:
        line = line.decode('utf-8')
        if not line.startswith('#') and line.find("MATCH") != -1:
            match_lines.append(line)

    if len(match_lines) > 0:
        with open(out_fp, 'w') as out_fh:
            for line in match_lines:
                print(line, file=out_fh)

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
