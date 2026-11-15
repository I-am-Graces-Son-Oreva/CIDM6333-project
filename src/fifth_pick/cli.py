import json
import sys
from collections.abc import Sequence

from fifth_pick import __version__

USAGE = "usage: fifth-pick <command>\n\ncommands:\n  health\n"
HEALTH = {
    "package": "fifth_pick",
    "status": "ok",
    "version": __version__,
}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    if arguments == ["health"]:
        print(json.dumps(HEALTH, sort_keys=True))
        return 0

    print(USAGE, file=sys.stderr)
    return 2
