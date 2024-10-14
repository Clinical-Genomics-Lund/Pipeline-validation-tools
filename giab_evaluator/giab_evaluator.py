#!/usr/bin/env python3

import argparse
from pathlib import Path
import logging
from configparser import ConfigParser
from typing import (
    List,
    Optional,
    Dict,
    Set,
)
from collections import defaultdict
import difflib

from util import (
    Comparison,
    ScoredVariant,
    PathObj,
    any_is_parent,
    do_comparison,
    parse_vcf,
    get_files_ending_with,
    get_single_file_ending_with,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger(__name__)


RUN_ID_PLACEHOLDER = "RUNID"
VCF_SUFFIX = [".vcf", ".vcf.gz"]

# Used to make the comparison function generic for PathObj and str


description = """
Compare results for runs in the CMD constitutional pipeline.

Performs all or a subset of the comparisons:

- What files are present
- Do the VCF files have the same number of variants
- For the scored SNV and SV VCFs, what are call differences and differences in rank scores
- Are there differences in the Scout yaml
"""


def main(
    run_id1: Optional[str],
    run_id2: Optional[str],
    results1_dir: Path,
    results2_dir: Path,
    config_path: str,
    comparisons: Optional[Set[str]],
    show_sub_scores: bool,
    score_threshold: int,
):

    config = ConfigParser()
    config.read(config_path)

    if run_id1 is None:
        run_id1 = str(results1_dir.name)
        LOG.info(f"--run_id1 not set, assigned: {run_id1}")

    if run_id2 is None:
        run_id2 = str(results2_dir.name)
        LOG.info(f"--run_id2 not set, assigned: {run_id2}")

    r1_paths = get_files_in_dir(results1_dir, run_id1, RUN_ID_PLACEHOLDER, results1_dir)
    r2_paths = get_files_in_dir(results2_dir, run_id2, RUN_ID_PLACEHOLDER, results2_dir)

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
        LOG.info("--- Comparing VCF numbers ---")
        is_vcf_pattern = ".vcf$|.vcf.gz$"
        r1_vcfs = get_files_ending_with(is_vcf_pattern, r1_paths)
        r2_vcfs = get_files_ending_with(is_vcf_pattern, r2_paths)
        if len(r1_vcfs) > 0 or len(r2_vcfs) > 0:
            compare_vcfs(
                r1_vcfs, r2_vcfs, run_id1, run_id2, str(results1_dir), str(results2_dir)
            )
        else:
            LOG.warning("No VCFs detected, skipping VCF comparison")

    if comparisons is None or "score" in comparisons:
        LOG.info("--- Comparing scored SNV VCFs ---")
        r1_scored_snv_vcf = get_single_file_ending_with(
            config["settings"]["scored_snv"], r1_paths, LOG
        )
        r2_scored_snv_vcf = get_single_file_ending_with(
            config["settings"]["scored_snv"], r2_paths, LOG
        )
        if r1_scored_snv_vcf and r2_scored_snv_vcf:
            variant_comparison(
                r1_scored_snv_vcf, r2_scored_snv_vcf, show_sub_scores, score_threshold
            )
        else:
            LOG.warning("Skipping VCF comparison")

    # FIXME: Annotation comparison

    if comparisons is None or "score_sv" in comparisons:
        LOG.info("--- Comparing scored SV VCFs ---")
        r1_scored_sv_vcf = get_single_file_ending_with(
            config["settings"]["scored_sv"], r1_paths, LOG
        )
        r2_scored_sv_vcf = get_single_file_ending_with(
            config["settings"]["scored_sv"], r1_paths, LOG
        )
        if r1_scored_sv_vcf and r2_scored_sv_vcf:
            variant_comparison(
                r1_scored_sv_vcf, r2_scored_sv_vcf, show_sub_scores, score_threshold
            )
        else:
            LOG.warning("Skipping scored SV VCF comparison")

    if comparisons is None or "yaml" in comparisons:
        LOG.info("--- Comparing YAML ---")
        yaml_pattern = config["settings"]["yaml"]
        r1_scored_yaml = get_single_file_ending_with(yaml_pattern, r1_paths, LOG)
        r2_scored_yaml = get_single_file_ending_with(yaml_pattern, r2_paths, LOG)
        if r1_scored_yaml and r2_scored_yaml:
            compare_yaml(r1_scored_yaml, r2_scored_yaml)
        else:
            LOG.warning("Skipping YAML comparison")


def compare_variant_score(
    shared_variants: Set[str],
    variants_r1: dict[str, ScoredVariant],
    variants_r2: dict[str, ScoredVariant],
    show_sub_scores: bool,
    score_threshold: int,
):
    class DiffScoredVariant:
        def __init__(self, r1: ScoredVariant, r2: ScoredVariant):
            self.r1 = r1
            self.r2 = r2

    diff_scored_variants: Dict[str, DiffScoredVariant] = {}

    for var_key in shared_variants:
        r1_variant = variants_r1[var_key]
        r2_variant = variants_r2[var_key]
        if r1_variant.rank_score != r2_variant.rank_score:
            diff_scored_variant = DiffScoredVariant(r1_variant, r2_variant)
            diff_scored_variants[var_key] = diff_scored_variant

    r1_above_thres_keys = [
        entry[0]
        for entry in diff_scored_variants.items()
        if entry[1].r1.rank_score is not None
        and entry[1].r1.rank_score >= score_threshold
    ]
    r2_above_thres_keys = [
        entry[0]
        for entry in diff_scored_variants.items()
        if entry[1].r2.rank_score is not None
        and entry[1].r2.rank_score >= score_threshold
    ]

    any_above_thres_keys = set(r1_above_thres_keys) | set(r2_above_thres_keys)
    diff_scored_any_above_thres = [
        diff_scored_variants[key] for key in any_above_thres_keys
    ]

    max_count = 30

    LOG.info(
        f"Number diffently scored above {score_threshold}: {len(diff_scored_any_above_thres)}"
    )
    if len(diff_scored_any_above_thres) > max_count:
        LOG.info(f"Only printing the {max_count} first")

    first_shared_key = list(shared_variants)[0]
    header_fields = ["chr", "pos", "var", "r1", "r2"]
    if show_sub_scores:
        for sub_score in variants_r1[first_shared_key].sub_scores:
            header_fields.append(f"r1_{sub_score}")
        for sub_score in variants_r2[first_shared_key].sub_scores:
            header_fields.append(f"r2_{sub_score}")
    print("\t".join(header_fields))
    for variant in sorted(
        diff_scored_any_above_thres,
        key=lambda var: var.r1.get_rank_score(),
        reverse=True,
    )[0:max_count]:
        fields = [
            variant.r1.chr,
            str(variant.r1.pos),
            f"{variant.r1.ref}/{variant.r1.alt}",
            variant.r1.get_rank_score_str(),
            variant.r2.get_rank_score_str(),
        ]
        if show_sub_scores:
            for sub_score_val in variant.r1.sub_scores.values():
                fields.append(str(sub_score_val))
            for sub_score_val in variant.r2.sub_scores.values():
                fields.append(str(sub_score_val))
        print("\t".join(fields))
        # f"{self.r1}\t{self.r1.get_rank_score_str()}\t{self.r2.rank_score}"


def compare_variant_presence(
    label_r1: str,
    label_r2: str,
    variants_r1: Dict[str, ScoredVariant],
    variants_r2: Dict[str, ScoredVariant],
    comparison_results: Comparison[str],
):

    r1_only = comparison_results.r1
    r2_only = comparison_results.r2
    common = comparison_results.shared

    LOG.info(f"In common: {len(common)}")
    LOG.info(f"Only in {label_r1}: {len(r1_only)}")
    LOG.info(f"Only in {label_r2}: {len(r2_only)}")

    max_display = 10
    LOG.info(f"First {min(len(r1_only), max_display)} only found in {label_r1}")
    for var in list(r1_only)[0:max_display]:
        print(variants_r1[var])
    LOG.info(f"First {min(len(r2_only), max_display)} only found in {label_r2}")
    for var in list(r2_only)[0:max_display]:
        print(variants_r2[var])

    # LOG.info(f"Number variants r1: {len(variants_r1)}")
    # LOG.info(f"Number variants r2: {len(variants_r2)}")


def compare_yaml(yaml_r1: PathObj, yaml_r2: PathObj):
    with yaml_r1.get_filehandle() as r1_fh, yaml_r2.get_filehandle() as r2_fh:
        r1_lines = r1_fh.readlines()
        r2_lines = r2_fh.readlines()

    diff = list(difflib.unified_diff(r1_lines, r2_lines))
    if len(diff) > 0:
        for line in diff:
            LOG.info(line.rstrip())
    else:
        LOG.info("No difference found")


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
        if vcf.check_valid_file(LOG):
            n_variants = count_variants(vcf)
        else:
            n_variants = 0
        r1_counts[str(vcf).replace(r1_base, "")] = n_variants

    r2_counts: Dict[str, int] = {}
    for vcf in r2_vcfs:
        if vcf.check_valid_file(LOG):
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


def get_files_in_dir(
    dir: Path,
    run_id: str,
    run_id_placeholder: str,
    base_dir: Path,
) -> List[PathObj]:
    processed_files_in_dir = [
        PathObj(path, run_id, run_id_placeholder, base_dir)
        for path in dir.rglob("*")
        if path.is_file()
    ]
    return processed_files_in_dir


def check_same_files(
    r1_dir: Path,
    r2_dir: Path,
    r1_paths: List[PathObj],
    r2_paths: List[PathObj],
    ignore_files: List[str],
):

    r1_label = str(r1_dir)
    r2_label = str(r2_dir)

    files_in_results1 = set(path.relative_path for path in r1_paths)
    files_in_results2 = set(path.relative_path for path in r2_paths)

    comparison = do_comparison(files_in_results1, files_in_results2)
    ignored: defaultdict[str, int] = defaultdict(int)

    # FIXME: Check the r2 / r1 which goes first, are things correct
    if len(comparison.r2) > 0:
        LOG.info(f"Files present in {r2_label} but missing in {r1_label}")
        for path in comparison.r2:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            LOG.info(f"  {path}")

    if len(comparison.r1) > 0:
        LOG.info(f"Files present in {r1_label} but missing in {r2_label}:")
        for path in comparison.r1:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            LOG.info(f"  {path}")

    if len(ignored) > 0:
        LOG.info("Ignored")
        for key, val in ignored.items():
            LOG.info(f"  {key}: {val}")


def variant_comparison(
    r1_scored_vcf: PathObj,
    r2_scored_vcf: PathObj,
    show_sub_scores: bool,
    score_threshold: int,
):
    variants_r1 = parse_vcf(r1_scored_vcf)
    variants_r2 = parse_vcf(r2_scored_vcf)
    comparison_results = do_comparison(
        set(variants_r1.keys()),
        set(variants_r2.keys()),
    )
    compare_variant_presence(
        str(r1_scored_vcf.real_path),
        str(r2_scored_vcf.real_path),
        variants_r1,
        variants_r2,
        comparison_results,
    )
    shared_variants = comparison_results.shared
    compare_variant_score(
        shared_variants, variants_r1, variants_r2, show_sub_scores, score_threshold
    )


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
    parser.add_argument("--show_sub_scores", action="store_true")
    parser.add_argument(
        "--score_threshold",
        type=int,
        help="Limit score comparisons to above this threshold",
        default=17,
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
        args.show_sub_scores,
        args.score_threshold,
    )
