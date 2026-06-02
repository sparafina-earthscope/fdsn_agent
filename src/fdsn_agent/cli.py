"""Command-line interface for fdsn-agent."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap

from fdsn_agent.agent import Agent
from fdsn_agent.config import PRESETS, LLMConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fdsn-agent",
        description="Headless FDSN archive agent — returns JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            environment variables:
              LLM_BASE_URL   override API base URL
              LLM_MODEL      override model name
              LLM_API_KEY    API key (preferred over --api-key)
              LLM_FORMAT     anthropic | openai

            examples:
              fdsn-agent "Find M6+ earthquakes in Japan in 2024"
              fdsn-agent --provider ollama --model llama3.1 "Stations near Anchorage"
              fdsn-agent --provider groq --pretty "What channels does IU.ANMO have?"
              fdsn-agent --base-url http://localhost:8000/v1 --model mymodel "Cascadia seismicity"
              echo "Noto waveforms" | fdsn-agent -
        """),
    )

    p.add_argument(
        "query", nargs="?",
        help="Natural-language query.  Use '-' to read from stdin.",
    )
    p.add_argument(
        "--provider", default="openai",
        choices=list(PRESETS), metavar="PROVIDER",
        help=f"LLM backend preset ({', '.join(PRESETS)}).  Default: openai",
    )
    p.add_argument("--base-url",    dest="base_url",    default=None,
                   help="Override API base URL")
    p.add_argument("--model",                           default=None,
                   help="Override model name")
    p.add_argument("--api-key",     dest="api_key",     default=None,
                   help="Override API key (prefer LLM_API_KEY env var)")
    p.add_argument("--format",                          default=None,
                   choices=["anthropic", "openai"],
                   help="Override wire format")
    p.add_argument("--max-tokens",  dest="max_tokens",  default=None, type=int,
                   help="Max tokens for LLM response (default: 1024)")
    p.add_argument("--temperature",                     default=None, type=float,
                   help="LLM temperature (default: 0.2)")
    p.add_argument("--pretty",      action="store_true",
                   help="Pretty-print JSON output")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Log agent steps to stderr")
    p.add_argument("--list-providers", action="store_true",
                   help="Print available provider presets as JSON and exit")
    return p


def _build_config(args: argparse.Namespace) -> LLMConfig:
    cfg = LLMConfig.from_env(args.provider)
    if args.base_url:    cfg.base_url    = args.base_url
    if args.model:       cfg.model       = args.model
    if args.api_key:     cfg.api_key     = args.api_key
    if args.format:      cfg.format      = args.format         # type: ignore[assignment]
    if args.max_tokens:  cfg.max_tokens  = args.max_tokens
    if args.temperature is not None:
                         cfg.temperature = args.temperature
    return cfg


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv)

    if args.list_providers:
        print(json.dumps(PRESETS, indent=2))
        return 0

    if args.verbose:
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG,
            format="[%(levelname)s %(name)s] %(message)s",
        )
    else:
        logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

    # ── Read query ──────────────────────────────────────────────────────
    if args.query == "-" or (args.query is None and not sys.stdin.isatty()):
        query = sys.stdin.read().strip()
    elif args.query:
        query = args.query.strip()
    else:
        parser.print_help()
        return 1

    if not query:
        print(json.dumps({"error": "empty query"}), file=sys.stderr)
        return 1

    cfg   = _build_config(args)
    agent = Agent(cfg)

    try:
        result = agent.query(query)
    except Exception as exc:  # noqa: BLE001
        out = {"error": str(exc), "query": query}
        print(json.dumps(out, indent=2 if args.pretty else None), file=sys.stderr)
        return 1

    print(result.to_json(pretty=args.pretty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
