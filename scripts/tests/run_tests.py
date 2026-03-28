#!/usr/bin/env python3
"""
Zhihu markdown feature tests.

Pushes each test/data/*.md file as a draft to a target article,
fetches the preview HTML, parses it back, and diffs vs the original.

Usage:
  uv run python scripts/tests/run_tests.py --article-id <ID> [--delay SECONDS] [--test NAME]
"""

import argparse
import difflib
import re
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from zhihu_client import (
    ZHUANLAN_API,
    ZHUANLAN_HEADERS,
    ZhihuClient,
    markdown_to_html,
    read_markdown_document,
)
from zhihu_parser import Parser

DATA_DIR = Path(__file__).resolve().parent / "data"
PREVIEW_URL = "https://zhuanlan.zhihu.com/p/{id}/preview?comment=0&catalog=1"

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(text: str) -> list[str]:
    lines = [l.rstrip() for l in text.splitlines()]
    out: list[str] = []
    prev_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and prev_blank:
            continue
        out.append(line)
        prev_blank = blank
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def _http_norm(lines: list[str]) -> list[str]:
    return [l.replace("https://", "http://") for l in lines]


def _img_norm(lines: list[str]) -> list[str]:
    """Normalize Zhihu image URLs: strip query params and subdomain variant.
    e.g. picx.zhimg.com/v2-abc_720w.jpg?source=xxx -> pic.zhimg.com/v2-abc
    """

    def _norm_url(m: re.Match) -> str:
        url = m.group(1)
        url = re.sub(r"\?.*$", "", url)  # strip query string
        url = re.sub(r"_(r|720w|1440w)\.", ".", url)  # strip size suffix
        url = re.sub(
            r"pic[a-z0-9]*\.zhimg\.com", "pic.zhimg.com", url
        )  # normalise subdomain
        return url

    return [re.sub(r"(?<=\()([^)]*zhimg\.com[^)]*)", _norm_url, l) for l in lines]


def colour_diff(diff: list[str]) -> str:
    out = []
    for line in diff:
        if line.startswith("---") or line.startswith("+++"):
            out.append(BOLD + line + RESET)
        elif line.startswith("-"):
            out.append(RED + line + RESET)
        elif line.startswith("+"):
            out.append(GREEN + line + RESET)
        elif line.startswith("@@"):
            out.append(CYAN + line + RESET)
        else:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def run_test(
    client: ZhihuClient,
    article_id: str,
    md_path: Path,
    delay: float,
) -> dict:
    name = md_path.stem
    body = md_path.read_text(encoding="utf-8")

    html = markdown_to_html(body)

    patch = client.session.patch(
        f"{ZHUANLAN_API}/{article_id}/draft",
        json={
            "content": html,
            "title": f"[test] {name}",
            "titleImage": "",
            "isTitleImageFullScreen": False,
            "table_of_contents": True,
        },
        headers=ZHUANLAN_HEADERS,
        timeout=30,
    )
    patch.raise_for_status()
    time.sleep(delay)

    preview = client.session.get(PREVIEW_URL.format(id=article_id), timeout=30)
    preview.raise_for_status()
    time.sleep(delay)

    parser = Parser()
    article = parser.parse_article_from_html(preview.text)
    rt_md = article.content.dump()

    local_lines = _img_norm(_http_norm(_normalise(body)))
    rt_lines = _img_norm(_http_norm(_normalise(rt_md)))

    diff = list(
        difflib.unified_diff(
            local_lines,
            rt_lines,
            fromfile="local",
            tofile="round-trip",
            lineterm="",
            n=2,
        )
    )
    return {"name": name, "diff": diff, "local": body, "rt": rt_md}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report(results: list[dict]) -> None:
    passed = [r for r in results if not r["diff"]]
    failed = [r for r in results if r["diff"]]

    print(f"\n{BOLD}=== Zhihu feature tests ==={RESET}")
    print(f"Passed: {len(passed)}  Failed: {len(failed)}  Total: {len(results)}\n")

    for r in passed:
        print(f"{GREEN}✓ {r['name']}{RESET}")

    for r in failed:
        added = sum(
            1 for l in r["diff"] if l.startswith("+") and not l.startswith("+++")
        )
        removed = sum(
            1 for l in r["diff"] if l.startswith("-") and not l.startswith("---")
        )
        print(f"\n{RED}✗ {r['name']}{RESET}  +{added}/-{removed} lines")
        print(colour_diff(r["diff"]))

    if failed:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--article-id", required=True, help="Zhihu article ID to use as test target"
    )
    p.add_argument("--delay", type=float, default=1.5, help="Seconds between requests")
    p.add_argument(
        "--test", default="", help="Run only tests matching this name pattern"
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    test_files = sorted(DATA_DIR.glob("*.md"))
    if args.test:
        test_files = [f for f in test_files if args.test in f.stem]
    if not test_files:
        print("No test files found.", file=sys.stderr)
        sys.exit(1)

    client = ZhihuClient.from_env_or_cache(allow_login=False)

    results: list[dict] = []
    for i, md_path in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] {md_path.stem} ...", end=" ", flush=True)
        try:
            result = run_test(client, args.article_id, md_path, args.delay)
            print("OK" if not result["diff"] else f"{len(result['diff'])} diff lines")
            results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(
                {"name": md_path.stem, "diff": [f"ERROR: {e}"], "local": "", "rt": ""}
            )

    report(results)


if __name__ == "__main__":
    main()
