from __future__ import annotations

import argparse
from pathlib import Path

from ._aggregation_common import AggregationError, HEADER, safe_int
from ._aggregation_excel import autosize_columns, default_output_path, generate_aggregations, write_excel
from ._aggregation_metrics import agg_metrics, build_hier_rows, median_int, range_str
from ._aggregation_records import get_param, parse_listing, read_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate aggregation sheet from results JSONL")
    parser.add_argument("--input", "-i", required=True, help="Path to results.jsonl")
    parser.add_argument("--output", "-o", default=None, help="Output xlsx path")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    output_path = Path(args.output) if args.output else None
    print(str(generate_aggregations(Path(args.input), output_path)))


__all__ = [
    "AggregationError",
    "HEADER",
    "agg_metrics",
    "autosize_columns",
    "build_arg_parser",
    "build_hier_rows",
    "default_output_path",
    "generate_aggregations",
    "get_param",
    "main",
    "median_int",
    "parse_listing",
    "range_str",
    "read_jsonl",
    "safe_int",
    "write_excel",
]
