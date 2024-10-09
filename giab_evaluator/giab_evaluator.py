#!/usr/bin/env python3

import argparse


def main():
    pass


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r1", "--results1", required=True)
    parser.add_argument("-r2", "--results2", required=True)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    main()
