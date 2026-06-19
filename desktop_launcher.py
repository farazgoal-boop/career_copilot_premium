"""Deprecated entry — redirects to premium_launcher (overlay + F2/F3)."""

from __future__ import annotations

import sys


def main() -> int:
    from premium_launcher import main as premium_main

    return premium_main()


if __name__ == "__main__":
    raise SystemExit(main())
