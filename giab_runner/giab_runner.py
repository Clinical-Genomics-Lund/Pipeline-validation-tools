#!/usr/bin/env python3

description = """
The intent of this script is to make running control samples on specific versions of pipelines easy.

The steps it performs:

1. Check out commit, tag or branch in target repo
2. Prepare CSV file for the run
3. Execute the pipeline

It can be configured to run singles, trios and start with FASTQ, BAM and VCF.
"""

import argparse
from pathlib import Path
import subprocess
import logging
from pathlib import Path
import sys
from logging import Logger
from configparser import ConfigParser
from typing import List, Dict, Optional
from datetime import datetime

from help_classes import Case, CsvEntry


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)


def main(
    config_path: str,
    label: Optional[str],
    checkout: str,
    base_dir: Path,
    wgs_repo: Path,
    start_data: str,
    dry_run: bool,
    stub_run: bool,
    run_type: str,
    skip_confirmation: bool,
    queue: Optional[str],
    no_start: bool,
):

    config = ConfigParser()
    config.read(config_path)

    check_valid_repo(LOG, wgs_repo)
    check_valid_checkout(LOG, wgs_repo, checkout)
    checkout_repo(wgs_repo, checkout)

    run_label = build_run_label(run_type, checkout, label, stub_run, start_data)

    results_dir = base_dir / run_label
    results_dir.mkdir(exist_ok=True, parents=True)

    run_log_path = results_dir / "run.log"
    write_run_log(run_log_path, run_type, label or "no label", checkout, config)

    if not config.getboolean(run_type, "trio"):
        csv = get_single_csv(config, run_label, run_type, start_data, queue)
    else:
        csv = get_trio_csv(config, run_label, run_type, start_data, queue)
    out_csv = results_dir / "run.csv"
    csv.write_to_file(str(out_csv))

    start_nextflow_command = build_start_nextflow_analysis_cmd(
        config["settings"]["start_nextflow_analysis"],
        out_csv,
        results_dir,
        stub_run,
        no_start,
    )

    start_run(start_nextflow_command, dry_run, skip_confirmation)

    setup_results_links(config, results_dir, run_label, run_type)


def build_run_label(
    run_type: str, checkout: str, label: Optional[str], stub_run: bool, start_data: str
) -> str:
    label_parts = [run_type]
    if label is not None:
        label_parts.append(label)
    label_parts.append(checkout)
    if stub_run:
        label_parts.append("stub")
    label_parts.append(start_data)
    run_label = "-".join(label_parts)
    return run_label


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


def get_single_csv(
    config: ConfigParser,
    run_label: str,
    run_type: str,
    start_data: str,
    queue: Optional[str],
):
    assay = config[run_type]["assay"]
    case_id = config[run_type]["case"]
    case_dict = config[case_id]
    case = parse_case(dict(case_dict), start_data, is_trio=False)

    if not Path(case.read1).exists() or not Path(case.read2).exists():
        raise FileNotFoundError(f"One or both files missing: {case.read1} {case.read2}")

    run_csv = CsvEntry(run_label, assay, [case], queue)
    return run_csv


def get_trio_csv(
    config: ConfigParser,
    run_label: str,
    run_type: str,
    start_data: str,
    queue: Optional[str],
):

    assay = config[run_type]["assay"]

    case_ids = config[run_type]["cases"].split(",")
    assert (
        len(case_ids) == 3
    ), f"For a trio, three fields are expected, found: {case_ids}"
    cases: List[Case] = []
    for case_id in case_ids:
        case_dict = config[case_id]
        case = parse_case(dict(case_dict), start_data, is_trio=True)

        if not Path(case.read1).exists() or not Path(case.read2).exists():
            raise FileNotFoundError(f"One or both files missing: {case.read1} {case.read2}")

        cases.append(case)

    run_csv = CsvEntry(run_label, assay, cases, queue)
    return run_csv


def parse_case(case_dict: Dict[str, str], start_data: str, is_trio: bool) -> Case:
    if start_data == "vcf":
        fw = case_dict["vcf"]
        rv = f"{fw}.tbi"
    elif start_data == "bam":
        fw = case_dict["bam"]
        rv = f"{fw}.bai"
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
        mother=case_dict.get("mother") if is_trio else None,
        father=case_dict.get("father") if is_trio else None,
    )
    return case


def build_start_nextflow_analysis_cmd(
    start_nextflow_analysis_pl: str,
    csv: Path,
    results_dir: Path,
    stub_run: bool,
    no_start: bool,
) -> List[str]:

    out_dir = results_dir
    cron_dir = results_dir

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

    if no_start:
        start_nextflow_command.append("--nostart")

    return start_nextflow_command


def start_run(
    start_nextflow_command: List[str], dry_run: bool, skip_confirmation: bool
):
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


def setup_results_links(
    config: ConfigParser, results_dir: Path, run_label: str, run_type: str
):

    assay = config[run_type]["assay"]

    log_base_dir = config["settings"]["log_base_dir"]
    trace_base_dir = config["settings"]["trace_base_dir"]
    work_base_dir = config["settings"]["work_base_dir"]

    current_date = datetime.now()
    date_stamp = current_date.strftime("%Y-%m-%d")

    log_link = results_dir / "nextflow.log"
    trace_link = results_dir / "trace.txt"
    work_link = results_dir / "work"

    log_link_target = Path(f"{log_base_dir}/{run_label}.{assay}.{date_stamp}.log")
    trace_link_target = Path(f"{trace_base_dir}/{run_label}.{assay}.trace.txt")
    work_link_target = Path(f"{work_base_dir}/{run_label}.{assay}")

    if log_link.exists():
        LOG.warning(f"{log_link} already exists, removing previous link")
        log_link.unlink()

    if trace_link.exists():
        LOG.warning(f"{trace_link} already exists, removing previous link")
        trace_link.unlink()

    if work_link.exists():
        LOG.warning(f"{work_link} already exists, removing previous link")
        work_link.unlink()

    log_link.symlink_to(log_link_target)
    trace_link.symlink_to(trace_link_target)
    work_link.symlink_to(work_link_target)


def parse_arguments():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--label", help="Something for you to use to remember the run")
    parser.add_argument(
        "--checkout",
        required=True,
        help="Tag, commit or branch to check out in --repo",
    )
    parser.add_argument(
        "--baseout",
        required=True,
        help="The base folder into which results folders are created following the pattern: {base}/{label}_{run_type}_{checkout})",
    )
    parser.add_argument(
        "--repo", required=True, help="Path to the Git repository of the pipeline"
    )
    parser.add_argument(
        "--start_data",
        default="fq",
        help="Start run from FASTQ (fq), BAM (bam) or VCF (vcf) (must be present in config)",
    )
    parser.add_argument(
        "--run_type",
        help="Select run type from the config (i.e. giab-single, giab-trio, seracare ...)",
        required=True,
    )
    parser.add_argument(
        "--dry",
        "-n",
        action="store_true",
        help="Go through the motions, but don't execute the pipeline",
    )
    parser.add_argument(
        "--skip_confirmation",
        action="store_true",
        help="If not set, you will be asked before starting the pipeline run",
    )
    parser.add_argument(
        "--stub", action="store_true", help="Pass the -stub-run flag to the pipeline"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Config file in INI format containing information about run types and cases",
    )
    parser.add_argument(
        "--queue",
        help="Optionally specify in which queue to run (i.e. low, grace-normal etc.)",
    )
    parser.add_argument(
        "--nostart",
        action="store_true",
        help="Run start_nextflow_analysis.pl with nostart, printing the path to the SLURM job only",
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    main(
        args.config,
        args.label,
        args.checkout,
        Path(args.baseout),
        Path(args.repo),
        args.start_data,
        args.dry,
        args.stub,
        args.run_type,
        args.skip_confirmation,
        args.queue,
        args.nostart,
    )
