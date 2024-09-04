#!/usr/bin/env python3

import argparse
import gzip
import re


class Variant:

    @staticmethod
    def parse_line(line: str, rank_categories: list[str]) -> "Variant":
        fields = line.split("\t")
        chrom = fields[0]
        pos = int(fields[1])
        ref = fields[3]
        alt = fields[4]
        info = fields[7]

        info_dict: dict[str, str] = {}
        for key_value in info.split(";"):
            (key, value) = key_value.split("=")
            info_dict[key] = value

        rank_score = int(info_dict["RankScore"].split(":")[1])
        rank_sub_results = [
            int(score) for score in info_dict["RankResult"].split("=")[1].split("|")
        ]

        assert len(rank_categories) == len(rank_sub_results)

        rank_sub_results_dict = dict(zip(rank_categories, rank_sub_results))

        return Variant(chrom, pos, ref, alt, rank_score, rank_sub_results_dict)

    def __init__(
        self,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        rank_score: int,
        rank_sub_scores: dict[str, int],
    ):
        self.chrom = chrom
        self.pos = pos
        self.ref = ref
        self.alt = alt
        self.rank_score = rank_score
        self.rank_sub_scores = rank_sub_scores

    def get_key(self) -> str:
        return f"{self.chrom}:{self.pos}_{self.ref}_{self.alt}"


def main(old_vcf_path: str, new_vcf_path: str):
    print(f"old_vcf: {old_vcf_path}")
    print(f"new_vcf: {new_vcf_path}")

    print("Parsing old vcf ...")
    old_vcf = parse_vcf(old_vcf_path)
    print("Parsing new vcf ...")
    new_vcf = parse_vcf(new_vcf_path)

    old_only = set(old_vcf.keys()).difference(set(new_vcf.keys()))
    new_only = set(new_vcf.keys()).difference(set(old_vcf.keys()))

    print(f"Total number old: {len(old_vcf)}")
    print(f"Total number new: {len(new_vcf)}")
    print(f"Number old only: {len(old_only)}")
    print(f"Number new only: {len(new_only)}")


def parse_vcf(path: str) -> dict[str, Variant]:

    rank_score_subcats = ""

    variants: dict[str, Variant] = {}
    with gzip.open(path, "rt") as in_fh:
        for line in in_fh:
            line = line.rstrip()
            if line.startswith("#"):
                match = re.search(r'Description="([^"]+)"', line)
                if match is not None:
                    match_text = str(match.group(1))
                    rank_score_subcats = match_text.split("|")
                else:
                    continue

            if rank_score_subcats == "":
                raise ValueError(
                    "Unexpected situation, header field 'RankResult' not found"
                )

            variant = Variant.parse_line(line, rank_score_subcats)
            variant_key = variant.get_key()
            variants[variant_key] = variant
    return variants


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old_vcf", required=True)
    parser.add_argument("--new_vcf", required=True)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    main(old_vcf_path=args.old_vcf, new_vcf_path=args.new_vcf)
