#!/usr/bin/env python3

description = """
Document here

Starting point: Run GIAB (or other sample) in a target repo
End point: Results in a controlled location, ready for further evaluation
"""

import argparse
from pathlib import Path
import subprocess
import logging
import configparser
from pathlib import Path
import sys
from logging import Logger
from configparser import ConfigParser
from typing import List, Dict

from help_classes import Case, CsvEntry


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)


def main(
    config_path: str,
    label: str,
    checkout: str,
    base_dir: Path,
    wgs_repo: Path,
    start_data: str,
    dry_run: bool,
    stub_run: bool,
    run_type: str,
    skip_confirmation: bool,
):

    config = configparser.ConfigParser()
    config.read(config_path)

    check_valid_repo(LOG, wgs_repo)
    check_valid_checkout(LOG, wgs_repo, checkout)

    # Code is primed and ready for running
    checkout_repo(wgs_repo, checkout)

    if not stub_run:
        run_label = f"{run_type}-{label}-{checkout}"
    else:
        run_label = f"{run_type}-{label}-{checkout}-stub"

    results_dir = base_dir / run_label
    results_dir.mkdir(exist_ok=True, parents=True)

    # Setup for execution
    run_log_path = results_dir / "run.log"
    write_run_log(run_log_path, run_type, label, checkout, config)

    # CSV
    if not config.getboolean(run_type, "trio"):
        csv = get_single_csv(config, run_label, run_type, start_data)
    else:
        csv = get_trio_csv(config, run_label, run_type, start_data)
    out_csv = results_dir / "giab.csv"
    csv.write_to_file(str(out_csv))

    start_nextflow_command = build_start_nextflow_analysis_cmd(
        config["settings"]["start_nextflow_analysis"],
        out_csv,
        results_dir,
        stub_run,
    )

    joined_command = " ".join(start_nextflow_command)
    if not dry_run:
        if not skip_confirmation:
            confirmation = input(
                f"Do you want to run the following command:\n{joined_command}\n(y/n) "
            )

            if confirmation == "y":
                subprocess.run(start_nextflow_command, check=True)
            else:
                LOG.info("Exiting ...")
    else:
        LOG.info(joined_command)


def checkout_repo(repo: Path, commit: str):

    LOG.info(f"Checking out: {commit} in {str(repo)}")
    results = subprocess.run(
        ["git", "checkout", commit],
        cwd=str(repo),
        # text=True is supported from Python 3.7
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if results.returncode != 0:
        LOG.error(results.stderr)


def check_git_id(repo: Path) -> str:
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=str(repo),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    first_line = result.stdout.splitlines()[0]
    commit_hash = first_line.split(" ")[0]
    return commit_hash


def check_valid_repo(logger: Logger, repo: Path):
    if not repo.exists():
        logger.error(f'The folder "{repo}" does not exist')
        sys.exit(1)

    if not repo.is_dir():
        logger.error(f'"{repo}" is not a folder')
        sys.exit(1)

    if not (repo / ".git").is_dir():
        logger.error(f'"{repo}" has no .git subdir. It should be a Git repository')
        sys.exit(1)


def check_valid_checkout(logger: Logger, repo: Path, checkout_obj: str):
    results = subprocess.run(
        ["git", "rev-parse", "--verify", checkout_obj],
        cwd=str(repo),
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not results.returncode == 0:
        logger.error(f"The string {checkout_obj} was not found in the repository")
        sys.exit(1)


def write_run_log(
    run_log_path: Path, run_type: str, tag: str, commit: str, config: ConfigParser
):
    with run_log_path.open("w") as out_fh:
        print(f"Run type: {run_type}", file=out_fh)
        print(f"tag: {tag}", file=out_fh)
        print(f"Commit: {commit}", file=out_fh)

        print("Config file - settings", file=out_fh)
        for key, val in config["settings"].items():
            print(f"{key}: {val}", file=out_fh)

        print(f"Config file - {run_type}", file=out_fh)
        for key, val in config[run_type].items():
            print(f"{key}: {val}", file=out_fh)


def parse_case(case_dict: Dict[str, str], start_data: str) -> Case:
    if start_data == "vcf":
        fw = case_dict["vcf"]
        rv = case_dict["vcf_tbi"]
    elif start_data == "bam":
        fw = case_dict["bam"]
        rv = case_dict["bam_bai"]
    else:
        fw = case_dict["fq_fw"]
        rv = case_dict["fq_rv"]

    case = Case(
        case_dict["id"],
        case_dict["clarity_pool_id"],
        case_dict["clarity_sample_id"],
        case_dict["sex"],
        case_dict["type"],
        fw,
        rv,
        mother=case_dict.get("mother"),
        father=case_dict.get("father"),
    )
    return case


def get_single_csv(
    config: ConfigParser, run_label: str, run_type: str, start_data: str
):

    assay = config[run_type]["assay"]

    case_id = config[run_type]["case"]
    case_dict = config[case_id]
    case = parse_case(dict(case_dict), start_data)

    run_csv = CsvEntry(run_label, assay, [case])
    return run_csv


def get_trio_csv(
    config: ConfigParser,
    run_label: str,
    run_type: str,
    start_data: str,
):

    assay = config[run_type]["assay"]

    case_ids = config[run_type]["cases"].split(",")
    assert (
        len(case_ids) == 3
    ), f"For a trio, three fields are expected, found: {case_ids}"
    cases: List[Case] = []
    for case_id in case_ids:
        case_dict = config[case_id]
        case = parse_case(dict(case_dict), start_data)
        cases.append(case)

    run_csv = CsvEntry(run_label, assay, cases)
    return run_csv


def build_start_nextflow_analysis_cmd(
    start_nextflow_analysis_pl: str,
    csv: Path,
    results_dir: Path,
    stub_run: bool,
) -> List[str]:

    out_dir = results_dir / "results"
    cron_dir = results_dir / "cron"

    start_nextflow_command = [
        start_nextflow_analysis_pl,
        str(csv.resolve()),
        "--outdir",
        str(out_dir.resolve()),
        "--crondir",
        str(cron_dir.resolve()),
    ]
    if stub_run:
        start_nextflow_command.append("--custom_flags")
        start_nextflow_command.append("'-stub-run'")

    return start_nextflow_command


def parse_arguments():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--checkout", required=True, help="Tag or commit ID to check out"
    )
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--wgs_repo", required=True)
    parser.add_argument("--start_data", default="fq", help="fq|bam|vcf")
    parser.add_argument(
        "--run_type", help="giab_single|giab_trio|seracare", required=True
    )
    parser.add_argument(
        "--dry",
        "-n",
        action="store_true",
        help="Go through the motions, but don't execute the pipeline",
    )
    parser.add_argument("--skip_confirmation", action="store_true")
    parser.add_argument("--stub", action="store_true", help="Execute a stub run")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    main(
        args.config,
        args.label,
        args.checkout,
        Path(args.outdir),
        Path(args.wgs_repo),
        args.start_data,
        args.dry,
        args.stub,
        args.run_type,
        args.skip_confirmation,
    )
