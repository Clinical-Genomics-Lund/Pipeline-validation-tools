#!/usr/bin/env python3

import argparse
from pathlib import Path
import logging
from configparser import ConfigParser
from typing import List, Optional, Dict, TextIO
from collections import defaultdict
import gzip
import sys
import difflib

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)


RUN_ID_PLACEHOLDER = "RUNID"
VCF_SUFFIX = [".vcf", ".vcf.gz"]

description = """
Description
"""


class PathObj:
    def __init__(
        self,
        path: Path,
        run_id: str,
        id_placeholder: str,
        base_dir: Path,
        config: ConfigParser,
    ):
        self.real_name = path.name
        self.real_path = path

        self.shared_name = path.name.replace(run_id, id_placeholder)
        self.shared_path = path.with_name(self.shared_name)
        self.relative_path = self.shared_path.relative_to(base_dir)

        self.run_id = run_id
        self.id_placeholder = id_placeholder

        # self.suffix = path.suffix

        self.is_vcf = str(path).endswith(".vcf") or str(path).endswith(".vcf.gz")

        self.is_scored_snv = str(self.shared_path).endswith(
            config["settings"]["scored_snv"]
        )
        self.is_scored_sv = str(self.shared_path).endswith(
            config["settings"]["scored_sv"]
        )
        self.is_yaml = str(self.shared_path).endswith(config["settings"]["yaml"])

        self.is_gzipped = path.suffix.endswith(".gz")

    def check_valid_file(self) -> bool:
        try:
            if self.is_gzipped:
                with gzip.open(str(self.real_path), "rt") as fh:
                    fh.read(1)
            else:
                with open(str(self.real_path), "r") as fh:
                    fh.read(1)
        except:
            LOG.info(f"File {self.real_path} is not a valid file")
            return False
        return True

    def get_filehandle(self) -> TextIO:
        if self.is_gzipped:
            in_fh = gzip.open(str(self.real_path), "rt")
        else:
            in_fh = open(str(self.real_path), "r")
        return in_fh

    def __str__(self) -> str:
        return str(self.relative_path)


def main(
    run_id1: Optional[str],
    run_id2: Optional[str],
    results1_dir: Path,
    results2_dir: Path,
    config_path: str,
    skip_compare_vcfs: bool,
):
    config = ConfigParser()
    config.read(config_path)

    if run_id1 is None:
        run_id1 = str(results1_dir.name)
        LOG.info(f"--run_id1 not set, assigned: {run_id1}")

    if run_id2 is None:
        run_id2 = str(results2_dir.name)
        LOG.info(f"--run_id2 not set, assigned: {run_id2}")

    r1_paths = get_files_in_dir(
        results1_dir, run_id1, RUN_ID_PLACEHOLDER, results1_dir, config
    )
    r2_paths = get_files_in_dir(
        results2_dir, run_id2, RUN_ID_PLACEHOLDER, results2_dir, config
    )

    check_same_files(
        results1_dir,
        results2_dir,
        r1_paths,
        r2_paths,
        config.get("settings", "ignore").split(","),
    )

    r1_vcfs = [path for path in r1_paths if path.is_vcf]
    r2_vcfs = [path for path in r2_paths if path.is_vcf]

    if not skip_compare_vcfs:
        compare_vcfs(
            r1_vcfs, r2_vcfs, run_id1, run_id2, str(results1_dir), str(results2_dir)
        )

    # FIXME: Think about how to clean up this
    # r1_scored_snv_vcf = [vcf for vcf in r1_vcfs if vcf.is_scored_snv][0]
    # r2_scored_snv_vcf = [vcf for vcf in r1_vcfs if vcf.is_scored_snv][0]
    # r1_scored_sv_vcf = [vcf for vcf in r1_vcfs if vcf.is_scored_sv][0]
    # r2_scored_sv_vcf = [vcf for vcf in r1_vcfs if vcf.is_scored_sv][0]
    r1_scored_yaml = [path for path in r1_paths if path.is_yaml][0]
    r2_scored_yaml = [path for path in r2_paths if path.is_yaml][0]

    # compare_scored_snv(r1_scored_snv_vcf, r2_scored_snv_vcf)
    # compare_scored_sv(r1_scored_sv_vcf, r2_scored_sv_vcf)
    compare_yaml(r1_scored_yaml, r2_scored_yaml)


def compare_scored_snv(vcf_snv_r1: PathObj, vcf_snv_r2: PathObj):
    pass


def compare_scored_sv(vcf_sv_r1: PathObj, vcf_sv_r2: PathObj):
    pass


def compare_yaml(yaml_r1: PathObj, yaml_r2: PathObj):
    LOG.info("Compare YAML")
    with yaml_r1.get_filehandle() as r1_fh, yaml_r2.get_filehandle() as r2_fh:
        r1_lines = r1_fh.readlines()
        r2_lines = r2_fh.readlines()

        diff = difflib.unified_diff(r1_lines, r2_lines)
        for line in diff:
            LOG.info(line.rstrip())


def compare_vcfs(
    r1_vcfs: List[PathObj],
    r2_vcfs: List[PathObj],
    run_id1: str,
    run_id2: str,
    r1_base: str,
    r2_base: str,
):
    r1_counts: Dict[str, int] = {}
    for vcf in r1_vcfs:
        if vcf.check_valid_file():
            n_variants = count_variants(vcf)
        else:
            n_variants = 0
        r1_counts[str(vcf).replace(r1_base, "")] = n_variants

    r2_counts: Dict[str, int] = {}
    for vcf in r2_vcfs:
        if vcf.check_valid_file():
            n_variants = count_variants(vcf)
        else:
            n_variants = 0
        r2_counts[str(vcf).replace(r2_base, "")] = n_variants

    paths = r1_counts.keys() | r2_counts.keys()

    max_path_length = max(len(path) for path in paths)

    # FIXME: How does this adapt to different run_id lengths?
    LOG.info(f"{'Path':<{max_path_length}} {run_id1:>10} {run_id2:>10}")
    for path in paths:
        r1_val = r1_counts.get(path) or "-"
        r2_val = r2_counts.get(path) or "-"
        LOG.info(
            f"{path:<{max_path_length}} {r1_val:>{len(run_id1)}} {r2_val:>{len(run_id2)}}"
        )


def count_variants(vcf: PathObj) -> int:

    nbr_entries = 0
    with vcf.get_filehandle() as in_fh:
        for line in in_fh:
            line = line.rstrip()
            if line.startswith("#"):
                continue
            nbr_entries += 1

    return nbr_entries


def compare_annotations(r1_vcf: Path, r2_vcf: Path):
    pass


def get_files_in_dir(
    dir: Path,
    run_id: str,
    run_id_placeholder: str,
    base_dir: Path,
    config: ConfigParser,
) -> List[PathObj]:
    processed_files_in_dir = [
        PathObj(path, run_id, run_id_placeholder, base_dir, config)
        # process_file(path, run_id, run_id_placeholder)
        for path in dir.rglob("*")
        if path.is_file()
    ]
    return processed_files_in_dir


# def process_file(path: Path, run_id: str, id_placeholder: str) -> PathObj:
#     current_name = path.name
#     if not current_name.startswith(run_id):
#         return path

#     updated_name = current_name.replace(run_id, id_placeholder)
#     updated_path = path.with_name(updated_name)
#     return updated_path


def check_same_files(
    r1_dir: Path,
    r2_dir: Path,
    r1_paths: List[PathObj],
    r2_paths: List[PathObj],
    ignore_files: List[str],
):

    r1_label = str(r1_dir)
    r2_label = str(r2_dir)

    # files_in_results1 = set([path.relative_to(r1_dir) for path in r1_paths])
    # files_in_results2 = set([path.relative_to(r2_dir) for path in r2_paths])

    files_in_results1 = set(path.relative_path for path in r1_paths)
    files_in_results2 = set(path.relative_path for path in r2_paths)

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
    parser.add_argument("--skip_compare_vcfs", action="store_true")
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
        args.skip_compare_vcfs,
    )
