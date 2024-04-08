#!/usr/bin/env python3

import argparse
import subprocess
import pathlib
import shutil
import glob
from typing import List


def main():
    args = parse_arguments()

    if not args.skip_svdb and not check_svdb():
        print('"svdb" needs to be available in the PATH variable')
        print("If running on a cluster, you can run it as such:")
        print("singularity run -B <drive> <container> bash evaluate_run.sh <input csv> <outdir dir>")
        raise ValueError("SVDB must be present in PATH")

    if not args.skip_svdb:
        print(f"Running SVDB with bnd_distance {args.bnd_distance} and overlap {args.overlap}")
        print(f"Will write output to {args.outdir}")
        outdir_path = pathlib.Path(args.outdir)
        outdir_path.mkdir(parents=True, exist_ok=True)
        match_to_baselines(args.csv, args.outdir, args.force_svdb, args.bnd_distance, args.overlap)

    print_summary(args.outdir)


def match_to_baselines(csv_fp: str, outdir: str, force_svdb: bool, bnd_distance: int, overlap: float):
    first_line = True
    with open(csv_fp) as in_fh:
        for line in in_fh:
            if first_line:
                first_line = False
                continue
        
            line = line.rstrip()
            fields = line.split(",")
            label = fields[0]
            result_vcf = fields[1]
            baseline_vcf = fields[2]

            out_fp = f"{outdir}/{label}.query_out.vcf"
            out_baseline_fp = f"{out_fp}.baseline"
            write_baseline(baseline_vcf, out_baseline_fp)

            match_fp = f"{out_fp}.match"
            match_path = pathlib.Path(match_fp)
            if match_path.exists() and not force_svdb:
                print(f"{match_path} already exists, skipping")
            else:
                print(f"Looking for matches in {label}, writing to {match_fp}")
                run_svdb(bnd_distance, overlap, baseline_vcf, result_vcf, match_fp)


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

    if proc.stdout is None:
        raise ValueError("Unexpected None for stdout")

    match_lines = list()
    for line in proc.stdout:
        line = line.decode('utf-8')
        if not line.startswith('#') and line.find("MATCH") != -1:
            match_lines.append(line)

    if len(match_lines) > 0:
        with open(out_fp, 'w') as out_fh:
            for line in match_lines:
                print(line, file=out_fh)

def print_summary(outdir: str):
    headers = ['label', 'type', 'chr', 'pos', 'len', 'type', 'callers', 'rank_result', 'rank_score']

    pattern = f"{outdir}/*.match"
    for match_file in glob.glob(pattern):
        print_single_summary(match_file)


def print_single_summary(match_file: str):

    # print(match_file)

    match_file_path = pathlib.Path(match_file)
    label = match_file_path.stem

    assert match_file.endswith(".match")

    bare_path = match_file.replace(".match", "")
    match_content = get_content(match_file)
    baseline_path = f"{bare_path}.baseline"
    baseline_content = get_content(baseline_path)

    print(f"{baseline_path}: {len(baseline_content)}, {match_file_path}: {len(match_content)}")

    # match_nbr_lines = len(match_content)
    # base_nbr_lines = len(baseline_content)

    if len(baseline_content) == 1:
        base_chr = baseline_content[0].split('\t')[0]
        base_chr = baseline_content[0].split('\t')[1]
    
    if len(match_content) == 1:
        match_chr = match_content[0].split('\t')[0]
        base_chr = match_content[0].split('\t')[1]


def get_content(fp: str) -> List[str]:
    file_content = list()
    with open(fp, 'r') as in_fh:
        for line in in_fh:
            line = line.rstrip()
            file_content.append(line)
    return file_content


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--csv", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--bnd_distance", default=25000)
    parser.add_argument("--overlap", default=0.7)
    parser.add_argument("--force_svdb", action='store_true', help="Rerun all SVDB matches even if already present")
    parser.add_argument("--skip_svdb", action='store_true', help="Don't run SVDB matches at all")

    args = parser.parse_args()
    return args



if __name__ == "__main__":
    main()
