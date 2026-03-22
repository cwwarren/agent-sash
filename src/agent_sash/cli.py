from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from agent_sash.backend import start_server, stop_server
from agent_sash.config import load_config
from agent_sash.hook import decision_payload, evaluate_command, extract_bash_command, load_hook_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-sash")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("start")
    subparsers.add_parser("stop")
    hook_parser = subparsers.add_parser("claude-hook")
    hook_parser.add_argument("--allow", default=None, help="override allow threshold, e.g. '<0.4'")
    return parser


def run_start() -> int:
    config = load_config()
    status = start_server(config)
    print(status)
    return 0


def run_stop() -> int:
    config = load_config()
    status = stop_server(config)
    print(status)
    return 0


def parse_allow(raw: str) -> float:
    if not raw.startswith("<"):
        raise ValueError("must start with '<'")
    return float(raw[1:])


def run_claude_hook(args: argparse.Namespace) -> int:
    config = load_config()
    if args.allow is not None:
        try:
            threshold = parse_allow(args.allow)
        except ValueError as exc:
            print(f"--allow: invalid value {args.allow!r} ({exc}), expected '<float' e.g. '<0.4'", file=sys.stderr)
            return 1
        config = dataclasses.replace(config, allow_below=threshold)
    try:
        payload = load_hook_payload()
    except json.JSONDecodeError as exc:
        print(f"invalid hook json: {exc}", file=sys.stderr)
        return 1
    command = extract_bash_command(payload)
    if command is None:
        return 0
    response = evaluate_command(config, command)
    print(json.dumps(response))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "start":
        return run_start()
    if args.command == "stop":
        return run_stop()
    if args.command == "claude-hook":
        return run_claude_hook(args)
    raise RuntimeError(f"unknown command: {args.command}")
