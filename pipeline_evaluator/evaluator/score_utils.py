from typing import Set, List, Dict, Optional
from logging import Logger
from pathlib import Path

from .classes import DiffScoredVariant, ScoredVariant

from .evaluator import log_and_write


def print_score_tables(
    logger: Logger,
    out_path_above_thres: Optional[Path],
    out_path_all: Optional[Path],
    diff_scored_variants: List[DiffScoredVariant],
    score_threshold: int,
    above_thres_variants: List[DiffScoredVariant],
    max_count: int,
    shared_variants: Set[str],
    variants_r1: Dict[str, ScoredVariant],
    variants_r2: Dict[str, ScoredVariant],
    show_sub_scores: bool,
):
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
    header_fields_w_subscores = header_fields.copy()
    for sub_score in variants_r1[first_shared_key].sub_scores:
        header_fields_w_subscores.append(f"r1_{sub_score}")
    for sub_score in variants_r2[first_shared_key].sub_scores:
        header_fields_w_subscores.append(f"r2_{sub_score}")
    if show_sub_scores:
        logger.info("\t".join(header_fields_w_subscores))
    else:
        logger.info("\t".join(header_fields))

    # Only print a subset to STDOUT
    for variant in above_thres_variants[0:max_count]:
        comparison_str = variant.r1.get_comparison_str(variant.r2, show_sub_scores)
        logger.info(comparison_str)

    # Always print sub scores in output files
    sub_scores_in_file = True
    # Print all to the out dir
    print("\t".join(header_fields_w_subscores), file=out_above_thres)
    for variant in above_thres_variants:
        comparison_str = variant.r1.get_comparison_str(variant.r2, sub_scores_in_file)
        print(comparison_str, file=out_above_thres)

    print("\t".join(header_fields_w_subscores), file=out_all)
    for variant in diff_scored_variants:
        comparison_str = variant.r1.get_comparison_str(variant.r2, sub_scores_in_file)
        print(comparison_str, file=out_all)

    if out_above_thres:
        out_above_thres.close()
    if out_all:
        out_all.close()
