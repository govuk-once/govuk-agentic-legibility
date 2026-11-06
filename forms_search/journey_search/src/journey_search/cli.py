"""Run a search from the command line, without MCP, against the configured table.

JOURNEY_SEARCH_TABLE=<table> uv run journey-search "report a mosquito" --limit 5
"""

from __future__ import annotations

import argparse
import json

from journey_search.config import Settings
from journey_search.contract import DEFAULT_LIMIT
from journey_search.search import build_search


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args(argv)
    result = build_search(Settings.from_env()).search(args.query, args.limit)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
