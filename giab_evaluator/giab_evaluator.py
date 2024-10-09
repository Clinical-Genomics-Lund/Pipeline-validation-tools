#!/usr/bin/env python3

import argparse
from pathlib import Path


def main(results1: Path, results2: Path):
    check_same_files(results1, results2)


def check_same_files(results1: Path, results2: Path):
    files_in_results1 = {
        file.relative_to(results1) for file in results1.rglob("*") if file.is_file()
    }
    files_in_results2 = {
        file.relative_to(results2) for file in results2.rglob("*") if file.is_file()
    }

    common_files = files_in_results1 & files_in_results2
    missing_in_results2 = files_in_results2 - files_in_results1
    missing_in_results1 = files_in_results1 - files_in_results2

    print("Summary of file comparison:")
    print(f"Total files in {results1}: {len(files_in_results1)}")
    print(f"Total files in {results2}: {len(files_in_results2)}")
    print(f"Common files: {len(common_files)}")
    print(f"Files missing in {results1}: {len(missing_in_results1)}")
    print(f"Files missing in {results2} {len(missing_in_results2)}")

    if len(missing_in_results1) > 0:
        print(f"Files present in {results2} but missing in {results1}")
        for file in missing_in_results1:
            print(f"  {file}")

    if len(missing_in_results2) > 0:
        print(f"Files present in {results1} but missing in {results2}:")
        for file in missing_in_results2:
            print(f"  {file}")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results1", "-r1", required=True)
    parser.add_argument("--results2", "-r2", required=True)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    main(Path(args.results1), Path(args.results2))
