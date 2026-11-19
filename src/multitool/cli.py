import argparse
from importlib.metadata import version

from multitool.codec import decode, encode
from multitool.hash import hash_file, hash_text
from multitool.net import network_info
from multitool.units import convert


def main() -> int:
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
    args = parser.parse_args()
    exit_code = 0

    try:
        if args.command == "codec":
            result = (
                encode(args.scheme, args.text)
                if args.direction == "encode"
                else decode(args.scheme, args.text)
            )
        elif args.command == "units":
            result = format(convert(args.value, args.from_unit, args.to_unit), ".15g")
        elif args.command == "hash":
            if (args.text is None) == (args.file is None):
                parser.error("provide exactly one of text or --file")
            result = (
                hash_file(args.algorithm, args.file)
                if args.file is not None
                else hash_text(args.algorithm, args.text)
            )
            exit_code = int(args.verify is not None and result != args.verify.lower())
        else:
            result = "\n".join(f"{key}: {value}" for key, value in network_info(args.cidr).items())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(result)
    return exit_code
