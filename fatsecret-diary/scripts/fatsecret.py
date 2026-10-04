#!/usr/bin/env python3
"""Skill entry point: python scripts/fatsecret.py <command>  (see `-h`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fatsecret_connector.cli import main  # noqa: E402

main()
