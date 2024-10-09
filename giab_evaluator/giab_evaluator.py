#!/usr/bin/env python3

import argparse
from pathlib import Path
import logging
from configparser import ConfigParser
from typing import List
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)


RUN_ID_PLACEHOLDER = "RUNID"

description = """
Description
"""


def main(run_id1: str, run_id2: str, results1: Path, results2: Path, config_path: str):
    config = ConfigParser()
    config.read(config_path)

    check_same_files(
        run_id1,
        run_id2,
        results1,
        results2,
        config.get("settings", "ignore").split(","),
    )


def process_file(path: Path, run_id: str, id_placeholder: str) -> Path:
    current_name = path.name
    if not current_name.startswith(run_id):
        return path

    updated_name = current_name.replace(run_id, id_placeholder)
    updated_path = path.with_name(updated_name)
    return updated_path


def check_same_files(
    run_id1: str, run_id2: str, results1: Path, results2: Path, ignore_files: List[str]
):

    files_in_results1 = {
        process_file(file.relative_to(results1), run_id1, RUN_ID_PLACEHOLDER)
        for file in results1.rglob("*")
        if file.is_file()
    }
    files_in_results2 = {
        process_file(file.relative_to(results2), run_id2, RUN_ID_PLACEHOLDER)
        for file in results2.rglob("*")
        if file.is_file()
    }

    common_files = files_in_results1 & files_in_results2
    missing_in_results2 = files_in_results2 - files_in_results1
    missing_in_results1 = files_in_results1 - files_in_results2

    LOG.info("Summary of file comparison:")
    LOG.info(f"Total files in {results1}: {len(files_in_results1)}")
    LOG.info(f"Total files in {results2}: {len(files_in_results2)}")
    LOG.info(f"Common files: {len(common_files)}")

    ignored: defaultdict[str, int] = defaultdict(int)

    if len(missing_in_results1) > 0:
        LOG.info(f"Files present in {results2} but missing in {results1}")
        for path in missing_in_results1:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            LOG.info(f"  {path}")

    if len(missing_in_results2) > 0:
        LOG.info(f"Files present in {results1} but missing in {results2}:")
        for path in missing_in_results2:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            LOG.info(f"  {path}")

    if len(ignored) > 0:
        LOG.info("Ignored")
        for key, val in ignored.items():
            LOG.info(f"{key}: {val}")


def any_is_parent(path: Path, names: List[str]) -> bool:
    for parent in path.parents:
        if parent.name in names:
            return True
    return False


def parse_arguments():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--run_id1", "-i1", required=True)
    parser.add_argument("--run_id2", "-i2", required=True)
    parser.add_argument("--results1", "-r1", required=True)
    parser.add_argument("--results2", "-r2", required=True)
    parser.add_argument("--config", help="Additional configurations", required=True)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    main(
        args.run_id1,
        args.run_id2,
        Path(args.results1),
        Path(args.results2),
        args.config,
    )
