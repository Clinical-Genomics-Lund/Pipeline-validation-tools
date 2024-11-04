#!/usr/bin/env python3

import argparse

from runner.giab_runner import add_arguments as runner_add_arguments
from runner.giab_runner import main_wrapper as runner_main_wrapper
from evaluator.giab_evaluator import add_arguments as eval_add_arguments
from evaluator.giab_evaluator import main_wrapper as eval_main_wrapper


__version_info__ = ("1", "0", "0")
__version__ = ".".join(__version_info__)

def main():
    args = parse_arguments()

    if args.subcommand == "run":
        runner_main_wrapper(args)
    elif args.subcommand == "eval":
        eval_main_wrapper(args)
    else:
        raise ValueError(f"Unknown args.subcommand: {args.subcommand}")


def parse_arguments():
    parent_parser = argparse.ArgumentParser()
    parent_parser.add_argument("--version", action="version", version=f"%(prog)s ({__version__})")
    subparsers = parent_parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run")
    runner_add_arguments(run_parser)
    eval_parser = subparsers.add_parser("eval")
    eval_add_arguments(eval_parser)

    args = parent_parser.parse_args()
    return args


if __name__ == "__main__":
    main()
