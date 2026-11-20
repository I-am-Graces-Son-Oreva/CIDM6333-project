#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
exec uv run --offline --no-sync python final-project/scripts/course_demo.py
