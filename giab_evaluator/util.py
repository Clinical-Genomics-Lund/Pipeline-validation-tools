import logging
from pathlib import Path
import re
from typing import Dict, Generic, List, Set, TypeVar, Union

from classes import PathObj, ScoredVariant

T = TypeVar("T")


def setup_stdout_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    log_formatter = logging.Formatter("%(levelname)s: %(message)s")
    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(log_formatter)

    logger.addHandler(stdout_handler)
    return logger


def add_file_logger(logger: logging.Logger, log_path: str):
    log_formatter = logging.Formatter("%(levelname)s: %(message)s")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)


def get_files_ending_with(pattern: str, paths: List[PathObj]) -> List[PathObj]:
    re_pattern = re.compile(pattern)
    matching = [path for path in paths if re.search(re_pattern, str(path)) is not None]
    return matching


def get_single_file_ending_with(
    pattern: str, paths: List[PathObj]
) -> Union[PathObj, None]:
    matching = get_files_ending_with(pattern, paths)

    if len(matching) == 0:
        return None
    elif len(matching) > 1:
        raise ValueError(f"Only one matching file allowed, found: {matching}")
    return matching[0]


def any_is_parent(path: Path, names: List[str]) -> bool:
    """
    Among all parent dirs, does any match 'names'?
    Useful to filter files in ignored folders
    """
    for parent in path.parents:
        if parent.name in names:
            return True
    return False


class Comparison(Generic[T]):

    # After Python 3.7 a @dataclass can be used instead
    def __init__(self, r1: Set[T], r2: Set[T], shared: Set[T]):
        self.r1 = r1
        self.r2 = r2
        self.shared = shared


def do_comparison(set_1: Set[T], set_2: Set[T]) -> Comparison[T]:
    """Can compare both str and Path objects, thus the generics"""
    common = set_1 & set_2
    s1_only = set_1 - set_2
    s2_only = set_2 - set_1

    return Comparison(s1_only, s2_only, common)


def parse_vcf(vcf: PathObj) -> Dict[str, ScoredVariant]:

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
