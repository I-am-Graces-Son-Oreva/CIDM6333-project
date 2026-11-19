import argparse
from importlib.metadata import version


def main() -> None:
    parser = argparse.ArgumentParser(prog="mt")
    parser.add_argument("--version", action="version", version=version("multitool"))
    parser.add_subparsers(dest="command", required=True)
    parser.parse_args()
