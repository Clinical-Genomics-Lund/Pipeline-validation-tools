#!/usr/bin/env python3

import argparse
from io import TextIOWrapper
from pathlib import Path
from configparser import ConfigParser
from typing import (
    List,
    Optional,
    Dict,
    Set,
)
from collections import defaultdict
import difflib

from classes import DiffScoredVariant
from util import (
    Comparison,
    ScoredVariant,
    PathObj,
    add_file_logger,
    any_is_parent,
    count_variants,
    do_comparison,
    get_files_in_dir,
    parse_vcf,
    get_files_ending_with,
    get_single_file_ending_with,
    setup_stdout_logger,
)

logger = setup_stdout_logger()

RUN_ID_PLACEHOLDER = "RUNID"
VCF_SUFFIX = [".vcf", ".vcf.gz"]

description = """
Compare results for runs in the CMD constitutional pipeline.

Performs all or a subset of the comparisons:

- What files are present
- Do the VCF files have the same number of variants
- For the scored SNV and SV VCFs, what are call differences and differences in rank scores
- Are there differences in the Scout yaml
"""


def log_and_write(text: str, fh: Optional[TextIOWrapper]):
    logger.info(text)
    if fh is not None:
        print(text, file=fh)


def main(
    run_id1: Optional[str],
    run_id2: Optional[str],
    results1_dir: Path,
    results2_dir: Path,
    config_path: str,
    comparisons: Optional[Set[str]],
    show_sub_scores: bool,
    score_threshold: int,
    max_display: int,
    outdir: Optional[Path],
):

    config = ConfigParser()
    config.read(config_path)

    if not results1_dir.exists() or not results2_dir.exists():
        r1_exists = results1_dir.exists()
        r2_exists = results2_dir.exists()
        raise ValueError(
            f"Both results dir must exist. Currently r1: {r1_exists} r2: {r2_exists}"
        )

    if outdir is not None:
        outdir.mkdir(parents=True, exist_ok=True)
        log_file = outdir / "out.log"
        add_file_logger(logger, str(log_file))

    if run_id1 is None:
        run_id1 = str(results1_dir.name)
        logger.info(f"--run_id1 not set, assigned: {run_id1}")

    if run_id2 is None:
        run_id2 = str(results2_dir.name)
        logger.info(f"--run_id2 not set, assigned: {run_id2}")

    r1_paths = get_files_in_dir(results1_dir, run_id1, RUN_ID_PLACEHOLDER, results1_dir)
    r2_paths = get_files_in_dir(results2_dir, run_id2, RUN_ID_PLACEHOLDER, results2_dir)

    if comparisons is None or "file" in comparisons:
        logger.info("--- Comparing existing files ---")
        out_path = outdir / "check_sample_files.txt" if outdir else None

        check_same_files(
            results1_dir,
            results2_dir,
            r1_paths,
            r2_paths,
            config.get("settings", "ignore").split(","),
            out_path,
        )

    if comparisons is None or "vcf" in comparisons:
        logger.info("--- Comparing VCF numbers ---")
        is_vcf_pattern = ".vcf$|.vcf.gz$"
        r1_vcfs = get_files_ending_with(is_vcf_pattern, r1_paths)
        r2_vcfs = get_files_ending_with(is_vcf_pattern, r2_paths)
        if len(r1_vcfs) > 0 or len(r2_vcfs) > 0:
            out_path = outdir / "all_vcf_compare.txt" if outdir else None
            compare_vcfs(
                r1_vcfs,
                r2_vcfs,
                run_id1,
                run_id2,
                str(results1_dir),
                str(results2_dir),
                out_path,
            )
        else:
            logger.warning("No VCFs detected, skipping VCF comparison")

    if comparisons is None or "score" in comparisons:
        logger.info("--- Comparing scored SNV VCFs ---")
        r1_scored_snv_vcf = get_single_file_ending_with(
            config["settings"]["scored_snv"], r1_paths
        )
        r2_scored_snv_vcf = get_single_file_ending_with(
            config["settings"]["scored_snv"], r2_paths
        )
        if r1_scored_snv_vcf and r2_scored_snv_vcf:
            out_path_presence = outdir / "scored_snv_presence.txt" if outdir else None
            out_path_score_thres = (
                outdir / f"scored_snv_score_thres_{score_threshold}.txt"
                if outdir
                else None
            )
            out_path_score_all = outdir / "scored_snv_score_all.txt" if outdir else None
            variant_comparison(
                r1_scored_snv_vcf,
                r2_scored_snv_vcf,
                show_sub_scores,
                score_threshold,
                max_display,
                out_path_presence,
                out_path_score_thres,
                out_path_score_all,
            )
        else:
            logger.warning(
                f"At least one scored SNV VCF missing. Looking for the pattern: {config['settings']['scored_snv']}"
            )

    if comparisons is None or "score_sv" in comparisons:
        logger.info("--- Comparing scored SV VCFs ---")
        r1_scored_sv_vcf = get_single_file_ending_with(
            config["settings"]["scored_sv"], r1_paths
        )
        r2_scored_sv_vcf = get_single_file_ending_with(
            config["settings"]["scored_sv"], r1_paths
        )
        if r1_scored_sv_vcf and r2_scored_sv_vcf:
            out_path_presence = outdir / "scored_sv_presence.txt" if outdir else None
            out_path_score_thres = (
                outdir / f"scored_sv_score_thres_{score_threshold}.txt"
                if outdir
                else None
            )
            out_path_score_all = outdir / "scored_sv_score.txt" if outdir else None
            variant_comparison(
                r1_scored_sv_vcf,
                r2_scored_sv_vcf,
                show_sub_scores,
                score_threshold,
                max_display,
                out_path_presence,
                out_path_score_thres,
                out_path_score_all,
            )
        else:
            logger.warning(
                f"At least one scored SV VCF missing. Looking for the pattern: {config['settings']['scored_sv']}"
            )

    if comparisons is None or "yaml" in comparisons:
        logger.info("--- Comparing YAML ---")
        yaml_pattern = config["settings"]["yaml"]
        r1_scored_yaml = get_single_file_ending_with(yaml_pattern, r1_paths)
        r2_scored_yaml = get_single_file_ending_with(yaml_pattern, r2_paths)
        if r1_scored_yaml and r2_scored_yaml:
            out_path = outdir / "yaml_diff.txt" if outdir else None
            compare_yaml(r1_scored_yaml, r2_scored_yaml, out_path)
        else:
            logger.warning(
                f"At least Scout YAML missing. Looking for the pattern: {config['settings']['yaml']}"
            )


def check_same_files(
    r1_dir: Path,
    r2_dir: Path,
    r1_paths: List[PathObj],
    r2_paths: List[PathObj],
    ignore_files: List[str],
    out_path: Optional[Path],
):

    r1_label = str(r1_dir)
    r2_label = str(r2_dir)

    files_in_results1 = set(path.relative_path for path in r1_paths)
    files_in_results2 = set(path.relative_path for path in r2_paths)

    comparison = do_comparison(files_in_results1, files_in_results2)
    ignored: defaultdict[str, int] = defaultdict(int)

    out_fh = open(out_path, "w") if out_path else None

    if len(comparison.r1) > 0:
        log_and_write(f"Files present in {r1_label} but missing in {r2_label}:", out_fh)
        for path in comparison.r1:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            log_and_write(f"  {path}", out_fh)

    if len(comparison.r2) > 0:
        log_and_write(f"Files present in {r2_label} but missing in {r1_label}", out_fh)
        for path in comparison.r2:
            if any_is_parent(path, ignore_files):
                ignored[str(path.parent)] += 1
                continue
            log_and_write(f"  {path}", out_fh)

    if len(ignored) > 0:
        log_and_write("Ignored", out_fh)
        for key, val in ignored.items():
            log_and_write(f"  {key}: {val}", out_fh)

    if out_fh:
        out_fh.close()


def compare_variant_presence(
    label_r1: str,
    label_r2: str,
    variants_r1: Dict[str, ScoredVariant],
    variants_r2: Dict[str, ScoredVariant],
    comparison_results: Comparison[str],
    max_display: int,
    out_path: Optional[Path],
):

    r1_only = comparison_results.r1
    r2_only = comparison_results.r2
    common = comparison_results.shared

    out_fh = open(out_path, "w") if out_path else None

    log_and_write(f"In common: {len(common)}", out_fh)
    log_and_write(f"Only in {label_r1}: {len(r1_only)}", out_fh)
    log_and_write(f"Only in {label_r2}: {len(r2_only)}", out_fh)

    # Only show max max_display in STDOUT
    logger.info(f"First {min(len(r1_only), max_display)} only found in {label_r1}")
    for var in list(r1_only)[0:max_display]:
        logger.info(str(variants_r1[var]))
    logger.info(f"First {min(len(r2_only), max_display)} only found in {label_r2}")
    for var in list(r2_only)[0:max_display]:
        logger.info(str(variants_r2[var]))

    # Write all to file
    print(f"Only found in {label_r1}", file=out_fh)
    for var in list(r1_only):
        print(str(variants_r1[var]), file=out_fh)
    print(
        f"First {min(len(r2_only), max_display)} only found in {label_r2}", file=out_fh
    )
    for var in list(r2_only):
        print(str(variants_r2[var]), file=out_fh)

    if out_fh:
        out_fh.close()


def variant_comparison(
    r1_scored_vcf: PathObj,
    r2_scored_vcf: PathObj,
    show_sub_scores: bool,
    score_threshold: int,
    max_display: int,
    out_path_presence: Optional[Path],
    out_path_score_above_thres: Optional[Path],
    out_path_score_all: Optional[Path],
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
        max_display,
        out_path_presence,
    )
    shared_variants = comparison_results.shared
    compare_variant_score(
        shared_variants,
        variants_r1,
        variants_r2,
        show_sub_scores,
        score_threshold,
        max_display,
        out_path_score_above_thres,
        out_path_score_all,
    )


def compare_vcfs(
    r1_vcfs: List[PathObj],
    r2_vcfs: List[PathObj],
    run_id1: str,
    run_id2: str,
    r1_base: str,
    r2_base: str,
    out_path: Optional[Path],
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

    out_fh = open(out_path, "w") if out_path else None
    log_and_write(f"{'Path':<{max_path_length}} {run_id1:>10} {run_id2:>10}", out_fh)
    for path in paths:
        r1_val = r1_counts.get(path) or "-"
        r2_val = r2_counts.get(path) or "-"
        log_and_write(
            f"{path:<{max_path_length}} {r1_val:>{len(run_id1)}} {r2_val:>{len(run_id2)}}",
            out_fh,
        )

    if out_fh:
        out_fh.close()


def compare_variant_score(
    shared_variants: Set[str],
    variants_r1: Dict[str, ScoredVariant],
    variants_r2: Dict[str, ScoredVariant],
    show_sub_scores: bool,
    score_threshold: int,
    max_count: int,
    out_path_above_thres: Optional[Path],
    out_path_all: Optional[Path],
):

    diff_scored_variants: List[DiffScoredVariant] = []

    for var_key in shared_variants:
        r1_variant = variants_r1[var_key]
        r2_variant = variants_r2[var_key]
        if r1_variant.rank_score != r2_variant.rank_score:
            diff_scored_variant = DiffScoredVariant(r1_variant, r2_variant)
            diff_scored_variants.append(diff_scored_variant)

    diff_scored_variants.sort(
        key=lambda var: var.r1.get_rank_score(),
        reverse=True,
    )

    above_thres_variants = [
        var for var in diff_scored_variants if var.any_above_thres(score_threshold)
    ]

    out_above_thres = open(out_path_above_thres, "w") if out_path_above_thres else None
    out_all = open(out_path_all, "w") if out_path_all else None

    logger.info(
        f"Number differently scored total: {len(diff_scored_variants)}",
    )
    logger.info(
        f"Number differently scored above {score_threshold}: {len(above_thres_variants)}",
    )
    if len(above_thres_variants) > max_count:
        log_and_write(f"Only printing the {max_count} first", out_above_thres)

    # Print header, optionally with sub scores
    first_shared_key = list(shared_variants)[0]
    header_fields = ["chr", "pos", "var", "r1", "r2"]
    if show_sub_scores:
        for sub_score in variants_r1[first_shared_key].sub_scores:
            header_fields.append(f"r1_{sub_score}")
        for sub_score in variants_r2[first_shared_key].sub_scores:
            header_fields.append(f"r2_{sub_score}")
    log_and_write("\t".join(header_fields), out_above_thres)

    # Only print a subset to STDOUT
    for variant in above_thres_variants[0:max_count]:
        comparison_str = variant.r1.get_comparison_str(variant.r2, show_sub_scores)
        logger.info(comparison_str)

    # Always print sub scores in output files
    sub_scores_in_file = True
    # Print all to the out dir
    for variant in above_thres_variants:
        comparison_str = variant.r1.get_comparison_str(variant.r2, sub_scores_in_file)
        print(comparison_str, file=out_above_thres)

    for variant in diff_scored_variants:
        comparison_str = variant.r1.get_comparison_str(variant.r2, sub_scores_in_file)
        print(comparison_str, file=out_all)

    if out_above_thres:
        out_above_thres.close()
    if out_all:
        out_all.close()


def compare_yaml(yaml_r1: PathObj, yaml_r2: PathObj, out_path: Optional[Path]):
    with yaml_r1.get_filehandle() as r1_fh, yaml_r2.get_filehandle() as r2_fh:
        r1_lines = r1_fh.readlines()
        r2_lines = r2_fh.readlines()

    out_fh = open(out_path, "w") if out_path else None
    diff = list(difflib.unified_diff(r1_lines, r2_lines))
    if len(diff) > 0:
        for line in diff:
            log_and_write(line.rstrip(), out_fh)
    else:
        log_and_write("No difference found", out_fh)
    if out_fh:
        out_fh.close()


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
    parser.add_argument(
        "--max_display",
        type=int,
        default=15,
        help="Max number of top variants to print to STDOUT",
    )
    parser.add_argument("--outdir", help="Optional output folder to store result files")
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
        args.max_display,
        Path(args.outdir) if args.outdir is not None else None,
    )
