"""Seller tool: convert a buyer request code into an activation code."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_licensing import generate_activation_code  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Career Copilot Premium activation code.")
    parser.add_argument("request_code", help="Buyer request code (CCP-XXXX-XXXX-XXXX-XXXX-XXXX)")
    args = parser.parse_args()
    try:
        activation_code = generate_activation_code(args.request_code)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1
    print(activation_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
