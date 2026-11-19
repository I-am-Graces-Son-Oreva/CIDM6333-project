import argparse
from importlib.metadata import version

from multitool.codec import decode, encode
from multitool.hash import hash_file, hash_text
from multitool.health import format_report, inspect_project
from multitool.net import network_info
from multitool.units import convert


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mt")
    parser.add_argument("--version", action="version", version=version("multitool"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    codec_parser = subparsers.add_parser("codec")
    codec_parser.add_argument("scheme", choices=("rot13", "base64", "hex"))
    codec_parser.add_argument("direction", choices=("encode", "decode"))
    codec_parser.add_argument("text")
    units_parser = subparsers.add_parser("units")
    units_parser.add_argument("value", type=float)
    units_parser.add_argument("from_unit")
    units_parser.add_argument("to_unit")
    hash_parser = subparsers.add_parser("hash")
    hash_parser.add_argument("algorithm", choices=("sha256", "md5"))
    hash_parser.add_argument("text", nargs="?")
    hash_parser.add_argument("--file")
    hash_parser.add_argument("--verify")
    net_parser = subparsers.add_parser("net")
    net_parser.add_argument("cidr")
    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("path")
    return parser


def _handle_codec(args: argparse.Namespace) -> str:
    return (
        encode(args.scheme, args.text)
        if args.direction == "encode"
        else decode(args.scheme, args.text)
    )


def _handle_units(args: argparse.Namespace) -> str:
    return format(convert(args.value, args.from_unit, args.to_unit), ".15g")


def _handle_hash(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[str, int]:
    if (args.text is None) == (args.file is None):
        parser.error("provide exactly one of text or --file")
    result = (
        hash_file(args.algorithm, args.file)
        if args.file is not None
        else hash_text(args.algorithm, args.text)
    )
    return result, int(args.verify is not None and result != args.verify.lower())


def _handle_net(args: argparse.Namespace) -> str:
    return "\n".join(f"{key}: {value}" for key, value in network_info(args.cidr).items())


def _handle_health(args: argparse.Namespace) -> tuple[str, int]:
    report = inspect_project(args.path)
    return format_report(report), report["exit_code"]


def _execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[str, int]:
    if args.command == "codec":
        return _handle_codec(args), 0
    if args.command == "units":
        return _handle_units(args), 0
    if args.command == "hash":
        return _handle_hash(args, parser)
    if args.command == "net":
        return _handle_net(args), 0
    return _handle_health(args)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        result, exit_code = _execute(args, parser)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(result)
    return exit_code
