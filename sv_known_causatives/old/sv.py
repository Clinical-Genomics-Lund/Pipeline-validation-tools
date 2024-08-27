#!/usr/bin/env python3

import argparse
import os
import subprocess


__version_info__ = ("1", "0", "0")
__version__ = ".".join(__version_info__)


def main():
    args = parse_arguments()

    # if args.subcommand == "setup_reference":
    #     pass
    if args.subcommand == "generate_samplesheets":
        subprocess.run(
            [
                "scripts/generate_samplesheets.sh",
                args.template,
                args.fastq_dir,
                args.out_dir,
            ]
        )
    elif args.subcommand == "start_run":
        subprocess.run(
            [
                "scripts/start_runs.sh",
                args.csvs_dir,
            ]
        )
    elif args.subcommand == "evaluate_run":
        subprocess.run(
            [
                "scripts/evaluate_run.sh",
                args.input_csv,
                args.output_dir,
            ]
        )
    else:
        raise ValueError(f"Unknown subcommand: {args.subcommand}")


def parse_arguments():
    parent_parser = argparse.ArgumentParser()
    parent_parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s (" + __version__ + ")"
    )

    subparsers = parent_parser.add_subparsers(dest="subcommand", required=True)

    add_generate_samplesheets(subparsers)
    start_runs(subparsers)
    evaluate_run(subparsers)

    args = parent_parser.parse_args()
    return args


# def add_setup_reference_data(subparsers):
#     parser = subparsers.add_parser("setup_reference")


def add_generate_samplesheets(subparsers):
    parser = subparsers.add_parser(
        "generate_samplesheets",
        description="Given a CSV template, it scans a folder with FASTQ files and generates CSV files for each matching pair.",
    )
    parser.add_argument("--template", required=True)
    parser.add_argument("--fastq_dir", required=True)
    parser.add_argument("--out_dir", required=True)


def start_runs(subparsers):
    parser = subparsers.add_parser("start_run", description="Start a folder with runs")
    parser.add_argument("--csvs_dir", required=True)


def evaluate_run(subparsers):
    parser = subparsers.add_parser(
        "evaluate_run",
        description="Given a CSV in the format label,result-vcf,baseline-vcf, check whether baseline variants are present in the result VCF using SVDB",
    )
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--output_dir", required=True)


if __name__ == "__main__":
    main()
