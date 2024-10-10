#!/usr/bin/env python3

import argparse
from pathlib import Path
import logging
from configparser import ConfigParser
from typing import List, Optional
from collections import defaultdict
import gzip

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)


RUN_ID_PLACEHOLDER = "RUNID"
VCF_SUFFIX = [".vcf", ".vcf.gz"]

description = """
Description
"""


def main(
    run_id1: Optional[str],
    run_id2: Optional[str],
    results1_dir: Path,
    results2_dir: Path,
    config_path: str,
):
    config = ConfigParser()
    config.read(config_path)

    if run_id1 is None:
        run_id1 = str(results1_dir.name)
        LOG.info(f"--run_id1 not set, assigned: {run_id1}")

    if run_id2 is None:
        run_id2 = str(results2_dir.name)
        LOG.info(f"--run_id2 not set, assigned: {run_id2}")

    r1_paths = get_files_in_dir(results1_dir, run_id1, RUN_ID_PLACEHOLDER)
    r2_paths = get_files_in_dir(results2_dir, run_id2, RUN_ID_PLACEHOLDER)

    check_same_files(
        results1_dir,
        results2_dir,
        r1_paths,
        r2_paths,
        config.get("settings", "ignore").split(","),
    )

    r1_vcfs = [path for path in r1_paths if path.suffix in VCF_SUFFIX]
    r2_vcfs = [path for path in r2_paths if path.suffix in VCF_SUFFIX]

    compare_vcfs(r1_vcfs, r2_vcfs, run_id1, run_id2)

    # compare_annotations()


def compare_vcfs(r1_vcfs: List[Path], r2_vcfs: List[Path], run_id1: str, run_id2: str):
    r1_counts = {}
    for vcf in r1_vcfs:
        is_gzipped = vcf.suffix == ".vcf.gz"
        path_str = str(vcf).replace(RUN_ID_PLACEHOLDER, run_id1)
        n_variants = count_variants(path_str, is_gzipped)
        r1_counts[path_str] = n_variants
    
    r2_counts = {}
    for vcf in r2_vcfs:
        is_gzipped = vcf.suffix == ".vcf.gz"
        path_str = str(vcf).replace(RUN_ID_PLACEHOLDER, run_id2)
        n_variants = count_variants(path_str, is_gzipped)
        r2_counts[path_str] = n_variants
    
    print(r1_counts)
    print(r2_counts)


def count_variants(vcf: str, is_gzipped: bool) -> int:
    print(f"Processing: {vcf}")
    if is_gzipped:
        in_fh = gzip.open(vcf, 'r')
    else:
        in_fh = open(vcf, 'rt')

    nbr_entries = 0
    for line in in_fh:
        line = line.rstrip()
        if line.startswith("#"):
            continue
        nbr_entries += 1

    in_fh.close()
    return nbr_entries
            
        


def compare_annotations(r1_vcf: Path, r2_vcf: Path):
    pass


def get_files_in_dir(dir: Path, run_id: str, run_id_placeholder: str) -> List[Path]:
    processed_files_in_dir = [
        process_file(path, run_id, run_id_placeholder)
        for path in dir.rglob("*")
        if path.is_file()
    ]
    return processed_files_in_dir


def process_file(path: Path, run_id: str, id_placeholder: str) -> Path:
    current_name = path.name
    if not current_name.startswith(run_id):
        return path

    updated_name = current_name.replace(run_id, id_placeholder)
    updated_path = path.with_name(updated_name)
    return updated_path


def check_same_files(
    r1_dir: Path,
    r2_dir: Path,
    r1_paths: List[Path],
    r2_paths: List[Path],
    ignore_files: List[str],
):
    
    r1_label = str(r1_dir)
    r2_label = str(r2_dir)

    files_in_results1 = set([path.relative_to(r1_dir) for path in r1_paths])
    files_in_results2 = set([path.relative_to(r2_dir) for path in r2_paths])

    common_files = files_in_results1 & files_in_results2
    missing_in_results2 = files_in_results2 - files_in_results1
    missing_in_results1 = files_in_results1 - files_in_results2

    LOG.info("Summary of file comparison:")
    LOG.info(f"Total files in {r1_label}: {len(files_in_results1)}")
    LOG.info(f"Total files in {r2_label}: {len(files_in_results2)}")
    LOG.info(f"Common files: {len(common_files)}")

    ignored: defaultdict[str, int] = defaultdict(int)

    if len(missing_in_results1) > 0:
        LOG.info(f"Files present in {r2_label} but missing in {r1_label}")
        for path in missing_in_results1:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            LOG.info(f"  {path}")

    if len(missing_in_results2) > 0:
        LOG.info(f"Files present in {r1_label} but missing in {r2_label}:")
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
    parser.add_argument(
        "--run_id1",
        "-i1",
        help="The group ID is used in some file names and can differ between runs. If not provided, it is set to the base folder name.",
    )
    parser.add_argument("--run_id2", "-i2", help="See --run_id1 help")
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
