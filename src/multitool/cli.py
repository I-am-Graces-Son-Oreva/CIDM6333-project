import argparse
from importlib.metadata import version

from multitool.codec import decode, encode
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
    args = parser.parse_args()

    try:
        if args.command == "codec":
            result = (
                encode(args.scheme, args.text)
                if args.direction == "encode"
                else decode(args.scheme, args.text)
            )
        else:
            result = format(convert(args.value, args.from_unit, args.to_unit), ".15g")
    except ValueError as exc:
        parser.error(str(exc))
    print(result)
    return 0
