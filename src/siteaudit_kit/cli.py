"""CLI with predictable exit statuses: 0 passed, 1 findings, 2 input/fetch error."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .audit import audit_html
from .fetch import fetch_url, validate_url
from .reporting import render
from .rules import RULES


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Audit one URL or local HTML file. No runtime dependencies.")
    p.add_argument("target", nargs="?", help="HTTP(S) URL or path to an HTML file")
    p.add_argument("--version", action="version", version=f"siteaudit-kit {__version__}")
    p.add_argument("--list-rules", action="store_true", help="list rule IDs, severities and descriptions")
    p.add_argument("--format", choices=("text", "json", "html", "sarif"), default="text")
    p.add_argument("--output", type=Path, help="write the report to this file (otherwise stdout)")
    p.add_argument("--fail-on", choices=("none", "info", "warning", "error"), default="error")
    p.add_argument("--ignore", default="", help="comma-separated rule IDs to skip")
    p.add_argument("--baseline", type=Path, help="only new findings affect exit status")
    p.add_argument("--write-baseline", type=Path, help="save fingerprints for deliberate acceptance")
    p.add_argument("--base-url", help="HTTP(S) page URL for URL checks on a local file")
    p.add_argument("--headers", type=Path, help="local file only: JSON object containing response headers")
    p.add_argument("--timeout", type=float, default=15, help="HTTP time budget in seconds (default: 15)")
    p.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024, help="file/response byte limit (default: 2 MiB)")
    p.add_argument("--allow-private", action="store_true", help="allow trusted local/private URL targets")
    return p


def _read_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _write(path: Path, contents: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def main(argv=None) -> int:
    p = parser()
    args = p.parse_args(argv)
    if args.list_rules:
        for rule in RULES.values():
            print(f"{rule.id}  {rule.severity:7}  {rule.title}")
        return 0
    if not args.target:
        p.error("target is required unless --list-rules is used")
    try:
        if not 1 <= args.max_bytes <= 8 * 1024 * 1024:
            raise ValueError("--max-bytes must be between 1 and 8 MiB")
        ignored = [s.strip() for s in args.ignore.split(",") if s.strip()]
        if set(ignored) - RULES.keys():
            raise ValueError("unknown ignored rule IDs: " + ", ".join(sorted(set(ignored) - RULES.keys())))
        remote = args.target.lower().startswith(("http://", "https://"))
        if remote:
            if args.headers or args.base_url:
                raise ValueError("--headers and --base-url apply only to local files")
            page = fetch_url(args.target, timeout=args.timeout, max_bytes=args.max_bytes,
                             allow_private=args.allow_private)
            report = audit_html(page.html, source=page.url, url=page.url, headers=page.headers, ignore=ignored)
        else:
            if args.base_url:
                validate_url(args.base_url)
            with Path(args.target).open("rb") as stream:
                content = stream.read(args.max_bytes + 1)
            if len(content) > args.max_bytes:
                raise ValueError("local file exceeds byte budget")
            headers = _read_json(args.headers) if args.headers else None
            if headers is not None and (not isinstance(headers, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
            )):
                raise ValueError("--headers must contain a JSON object of string names and string values")
            report = audit_html(content.decode("utf-8-sig"), source=Path(args.target).as_posix(),
                                url=args.base_url, headers=headers, ignore=ignored)
        if args.baseline:
            report.apply_baseline(_read_json(args.baseline))
        if args.write_baseline:
            _write(args.write_baseline, json.dumps(report.baseline(), indent=2) + "\n")
        output = render(report, args.format)
        if args.output:
            _write(args.output, output)
        else:
            sys.stdout.write(output)
        return 1 if report.fails(args.fail_on) else 0
    except (OSError, ValueError) as exc:
        # Untrusted filenames/server strings must not be able to inject terminal escapes.
        message = "".join(c if c.isprintable() else " " for c in str(exc))
        print("siteaudit: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
