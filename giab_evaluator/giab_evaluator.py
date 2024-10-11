#!/usr/bin/env python3

import argparse
from pathlib import Path
import logging
from configparser import ConfigParser
from typing import List, Optional, Dict, TextIO, Set, Tuple, TypeVar
from collections import defaultdict
import gzip
import sys
import difflib
import re
import itertools

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)


RUN_ID_PLACEHOLDER = "RUNID"
VCF_SUFFIX = [".vcf", ".vcf.gz"]

# Used to make the comparison function generic for PathObj and str
T = TypeVar("T")


description = """
Description
"""


class ScoredVariant:
    def __init__(
        self,
        chr: str,
        pos: int,
        ref: str,
        alt: str,
        rank_score: int | None,
        sub_scores: dict[str, int],
    ):
        self.chr = chr
        self.pos = pos
        self.ref = ref
        self.alt = alt
        self.rank_score = rank_score
        self.sub_scores = sub_scores

    def __str__(self) -> str:
        return f"{self.chr}:{self.pos} {self.ref}/{self.alt} (Score: {self.rank_score})"


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
    comparisons: Optional[Set[str]],
):

    # FIXME: Single variable "comparisons" defaulting to "all"?

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

    if comparisons is None or "file" in comparisons:
        LOG.info("--- Comparing existing files ---")
        check_same_files(
            results1_dir,
            results2_dir,
            r1_paths,
            r2_paths,
            config.get("settings", "ignore").split(","),
        )

    if comparisons is None or "vcf" in comparisons:
        r1_vcfs = [path for path in r1_paths if path.is_vcf]
        r2_vcfs = [path for path in r2_paths if path.is_vcf]
        LOG.info("--- Comparing VCF numbers ---")
        compare_vcfs(
            r1_vcfs, r2_vcfs, run_id1, run_id2, str(results1_dir), str(results2_dir)
        )

    if comparisons is None or "score" in comparisons:
        LOG.info("--- Comparing scored SNV VCFs ---")
        # FIXME: Cleanup
        r1_scored_snv_vcf = [vcf for vcf in r1_paths if vcf.is_scored_snv][0]
        r2_scored_snv_vcf = [vcf for vcf in r2_paths if vcf.is_scored_snv][0]
        compare_scored_snv(r1_scored_snv_vcf, r2_scored_snv_vcf)

    if comparisons is None or "score_sv" in comparisons:
        LOG.info("--- Comparing scored SV VCFs ---")
        # r1_scored_sv_vcf = [vcf for vcf in r1_vcfs if vcf.is_scored_sv][0]
        # r2_scored_sv_vcf = [vcf for vcf in r1_vcfs if vcf.is_scored_sv][0]

    if comparisons is None or "yaml" in comparisons:
        r1_scored_yaml = [path for path in r1_paths if path.is_yaml][0]
        r2_scored_yaml = [path for path in r2_paths if path.is_yaml][0]
        compare_yaml(r1_scored_yaml, r2_scored_yaml)


# FIXME: Next: Can I get the rank score categories from the VCF header?
def parse_vcf(vcf: PathObj) -> dict[str, ScoredVariant]:

    rank_score_pattern = re.compile("RankScore=.+:(-?\\w+);")
    rank_sub_scores_pattern = re.compile("RankResult=(-?\\d+(\\|-?\\d+)+)")
    sub_score_name_pattern = re.compile('ID=RankResult,.*Description="(.*)">')

    rank_sub_score_names = None

    variants: Dict[str, ScoredVariant] = {}
    with vcf.get_filehandle() as in_fh:
        for line in in_fh:
            line = line.rstrip()
            if line.startswith("#"):

                if rank_sub_score_names is None and line.startswith(
                    "##INFO=<ID=RankResult,"
                ):
                    match = sub_score_name_pattern.search(line)
                    if match is None:
                        raise ValueError(
                            f"Rankscore categories expected but not found in: ${line}"
                        )
                    match_string = match.group(1)
                    rank_sub_score_names = match_string.split("|")

                continue
            fields = line.split("\t")
            chr = fields[0]
            pos = int(fields[1])
            ref = fields[3]
            alt = fields[4]
            info = fields[7]
            rank_score_match = rank_score_pattern.search(info)

            rank_score = None
            if rank_score_match is not None:
                rank_score = int(rank_score_match.group(1))

            rank_sub_scores_match = rank_sub_scores_pattern.search(info)
            rank_sub_scores = None
            if rank_sub_scores_match is not None:
                rank_sub_scores = [
                    int(val) for val in rank_sub_scores_match.group(1).split("|")
                ]

            key = f"{chr}_{pos}_{ref}_{alt}"
            sub_scores_dict: Dict[str, int] = {}
            if rank_sub_scores is not None:
                if rank_sub_score_names is None:
                    raise ValueError("Found rank sub scores, but not header")
                assert len(rank_sub_score_names) == len(
                    rank_sub_scores
                ), f"Length of sub score names and values should match, found {rank_sub_score_names} and {rank_sub_scores_match} in line: {line}"
                sub_scores_dict = dict(zip(rank_sub_score_names, rank_sub_scores))
            variant = ScoredVariant(chr, pos, ref, alt, rank_score, sub_scores_dict)
            variants[key] = variant
    return variants


def compare_scored_snv(vcf_snv_r1: PathObj, vcf_snv_r2: PathObj):
    variants_r1 = parse_vcf(vcf_snv_r1)
    variants_r2 = parse_vcf(vcf_snv_r2)

    (r1_only, r2_only) = make_comparison(
        str(vcf_snv_r1.real_path),
        str(vcf_snv_r2.real_path),
        set(variants_r1.keys()),
        set(variants_r2.keys()),
        print_results=True,
    )

    max_display = 10
    LOG.info(
        f"First {min(len(r1_only), max_display)} only found in {vcf_snv_r1.real_path}"
    )
    for var in list(r1_only)[0:max_display]:
        print(variants_r1[var])
    LOG.info(
        f"First {min(len(r2_only), max_display)} only found in {vcf_snv_r2.real_path}"
    )
    for var in list(r2_only)[0:max_display]:
        print(variants_r2[var])

    # LOG.info(f"Number variants r1: {len(variants_r1)}")
    # LOG.info(f"Number variants r2: {len(variants_r2)}")


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
        for path in dir.rglob("*")
        if path.is_file()
    ]
    return processed_files_in_dir


def make_comparison(
    label1: str, label2: str, set_1: Set[T], set_2: Set[T], print_results: bool
) -> Tuple[Set[T], Set[T]]:
    common_files = set_1 & set_2
    s1_only = set_1 - set_2
    s2_only = set_2 - set_1

    if print_results:
        LOG.info(f"In common: {len(common_files)}")
        LOG.info(f"Only in {label1}: {len(s1_only)}")
        LOG.info(f"Only in {label2}: {len(s2_only)}")
    return (s1_only, s2_only)


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

    (r1_only, r2_only) = make_comparison(
        r1_label, r2_label, files_in_results1, files_in_results2, print_results=True
    )

    # common_files = files_in_results1 & files_in_results2
    # missing_in_results2 = files_in_results2 - files_in_results1
    # missing_in_results1 = files_in_results1 - files_in_results2

    # LOG.info("Summary of file comparison:")
    # LOG.info(f"Total files in {r1_label}: {len(files_in_results1)}")
    # LOG.info(f"Total files in {r2_label}: {len(files_in_results2)}")
    # LOG.info(f"Common files: {len(common_files)}")

    ignored: defaultdict[str, int] = defaultdict(int)

    if len(r2_only) > 0:
        LOG.info(f"Files present in {r2_label} but missing in {r1_label}")
        for path in r2_only:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            LOG.info(f"  {path}")

    if len(r1_only) > 0:
        LOG.info(f"Files present in {r1_label} but missing in {r2_label}:")
        for path in r1_only:
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
    parser.add_argument(
        "--comparisons",
        help="Comma separated. Defaults to: all i.e. file,vcf,score,score_sv,yaml",
        default="all",
    )
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
        None if args.comparisons == "all" else set(args.comparisons.split(",")),
    )
