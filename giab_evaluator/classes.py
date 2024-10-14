import gzip
from pathlib import Path
from typing import Dict, Optional, TextIO


class ScoredVariant:
    """Represents position, call and scores of a variant"""

    def __init__(
        self,
        chr: str,
        pos: int,
        ref: str,
        alt: str,
        rank_score: Optional[int],
        sub_scores: Dict[str, int],
    ):
        self.chr = chr
        self.pos = pos
        self.ref = ref
        self.alt = alt
        self.rank_score = rank_score
        self.sub_scores = sub_scores

    def __str__(self) -> str:
        return f"{self.chr}:{self.pos} {self.ref}/{self.alt} (Score: {self.rank_score})"

    def get_rank_score(self) -> int:
        if self.rank_score is None:
            raise ValueError(
                "Rank score not present, check before using 'get_rank_score'"
            )
        return self.rank_score

    def get_rank_score_str(self) -> str:
        return str(self.rank_score) if self.rank_score is not None else ""

    def get_comparison_str(
        self, comp_var: "ScoredVariant", show_sub_scores: bool
    ) -> str:

        if (
            self.chr != comp_var.chr
            or self.pos != comp_var.pos
            or self.ref != comp_var.ref
            or self.alt != comp_var.alt
        ):
            raise ValueError(
                f"Must compare the same variant. This: {str(self)} Other: {str(comp_var)}"
            )

        fields = [
            self.chr,
            str(self.pos),
            f"{self.ref}/{self.alt}",
            self.get_rank_score_str(),
            comp_var.get_rank_score_str(),
        ]
        if show_sub_scores:
            for sub_score_val in self.sub_scores.values():
                fields.append(str(sub_score_val))
            for sub_score_val in comp_var.sub_scores.values():
                fields.append(str(sub_score_val))
        return "\t".join(fields)


class PathObj:
    """
    Extended Path object to make comparison between results dir more convenient.

    1. Relative paths to the base dir
    2. Can replace the run ID with the string 'RUNID'
    3. Can detect whether a file is text or gzip
    """

    def __init__(
        self,
        path: Path,
        run_id: str,
        id_placeholder: str,
        base_dir: Path,
    ):
        self.real_name = path.name
        self.real_path = path

        self.shared_name = path.name.replace(run_id, id_placeholder)
        self.shared_path = path.with_name(self.shared_name)
        self.relative_path = self.shared_path.relative_to(base_dir)

        self.run_id = run_id
        self.id_placeholder = id_placeholder

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


class DiffScoredVariant:
    """Container for comparison of differently scored variants in the same location"""

    def __init__(self, r1_variant: ScoredVariant, r2_variant: ScoredVariant):

        self.r1 = r1_variant
        self.r2 = r2_variant

    def any_above_thres(self, score_threshold: int) -> bool:
        r1_above_thres = (
            self.r1.rank_score is not None and self.r1.rank_score >= score_threshold
        )
        r2_above_thres = (
            self.r2.rank_score is not None and self.r2.rank_score >= score_threshold
        )
        any_above_thres = r1_above_thres or r2_above_thres
        return any_above_thres
