#!/usr/bin/env python3
"""
Round-trip consistency check for all Zhihu articles.

Flow per article:
  local markdown → markdown_to_html → PATCH draft → fetch preview HTML
  → zhihu_parser → markdown → diff vs local

Usage:
  uv run python scripts/zhihu_roundtrip_check.py [--delay SECONDS] [--article-id ID]
"""

import argparse
import difflib
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zhihu_client import (
    ZHUANLAN_API,
    ZHUANLAN_HEADERS,
    ZhihuClient,
    markdown_to_html,
    read_markdown_document,
)
from zhihu_parser import Parser

ARTICLE_DIR = (
    Path(__file__).resolve().parent.parent
    / "website"
    / "content"
    / "zh-cn"
    / "articles"
)
PREVIEW_URL = "https://zhuanlan.zhihu.com/p/{id}/preview?comment=0&catalog=1"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _normalise(text: str) -> list[str]:
    """Return a list of stripped, de-duplicated-blank lines for diffing."""
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    prev_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and prev_blank:
            continue
        out.append(line)
        prev_blank = blank
    # drop leading/trailing blank lines
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


# ---------------------------------------------------------------------------
# Per-article check
# ---------------------------------------------------------------------------


def check_article(
    client: ZhihuClient,
    article_id: str,
    md_path: Path,
    delay: float,
) -> dict:
    metadata, body_markdown = read_markdown_document(md_path)
    title = metadata.get("title") or md_path.stem
    title_image = metadata.get("zhihu_title_image_url") or metadata.get(
        "title_image_url"
    )

    html = markdown_to_html(body_markdown)

    # Push draft
    patch = client.session.patch(
        f"{ZHUANLAN_API}/{article_id}/draft",
        json={
            "content": html,
            "title": title,
            "titleImage": title_image,
            "isTitleImageFullScreen": False,
            "table_of_contents": True,
        },
        headers=ZHUANLAN_HEADERS,
        timeout=30,
    )
    patch.raise_for_status()
    time.sleep(delay)

    # Fetch preview
    preview = client.session.get(PREVIEW_URL.format(id=article_id), timeout=30)
    preview.raise_for_status()
    time.sleep(delay)

    # Parse preview HTML → markdown
    parser = Parser()
    article = parser.parse_article_from_html(preview.text)
    round_trip_md = article.content.dump()

    local_lines = _normalise(body_markdown)
    rt_lines = _normalise(round_trip_md)

    def _apply_norms(lines: list[str]) -> list[str]:
        result = []
        for l in lines:
            # https → http (Zhihu preview rewrites all URLs)
            l = l.replace("https://", "http://")

            # Zhihu image URLs: normalise subdomain/size-suffix/query to just v2-hash
            def _norm_img_url(m: re.Match) -> str:
                url = m.group(1)
                url = re.sub(r"\?.*$", "", url)
                url = re.sub(r"_(r|720w|1440w|b)\.", ".", url)
                url = re.sub(r"pic[a-z0-9]*\.zhimg\.com", "pic.zhimg.com", url)
                return url

            l = re.sub(r"(?<=\()([^)]*zhimg\.com[^)]*)", _norm_img_url, l)
            # Emphasis markers: *text* ↔ _text_ are semantically equivalent
            l = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"_\1_", l)
            # Inline code: strip trailing spaces inside backticks
            l = re.sub(r"`([^`]+?) +`", r"`\1`", l)
            # Angle-bracket URLs: [text](<url>) → [text](url)
            l = re.sub(r"\(<(https?://[^>]+)>\)", r"(\1)", l)
            # Bare-URL links where label == URL: [url](url) → url
            l = re.sub(r"\[(http[^\]]+)\]\(\1\)", r"\1", l)
            # Trailing space in link labels: [label ](url) → [label](url)
            l = re.sub(r"\[([^\]]+?) +\]", r"[\1]", l)
            # Backslash escapes: \_ → _ (parser strips them, source may keep them)
            l = re.sub(r"\\([_*\[\]()~`>#+\-.!|{}])", r"\1", l)
            result.append(l)
        return result

    diff = list(
        difflib.unified_diff(
            _apply_norms(local_lines),
            _apply_norms(rt_lines),
            fromfile="local",
            tofile="round-trip",
            lineterm="",
            n=2,
        )
    )

    return {
        "article_id": article_id,
        "title": title,
        "diff": diff,
        "local_lines": local_lines,
        "rt_lines": rt_lines,
    }


# ---------------------------------------------------------------------------
# Categorise diff hunks
# ---------------------------------------------------------------------------

CATEGORIES = {
    "linkcard": re.compile(r"linkcard|{{<"),
    "image": re.compile(r"!\["),
    "code_block": re.compile(r"^[+-]```"),
    "heading": re.compile(r"^[+-]#{1,6} "),
    "list_item": re.compile(r"^[+-]\s*[-*\d]"),
    "bold_italic": re.compile(r"\*\*|__|\*[^*]|_[^_]"),
}


def categorise(diff: list[str]) -> set[str]:
    cats: set[str] = set()
    for line in diff:
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        for name, pat in CATEGORIES.items():
            if pat.search(line):
                cats.add(name)
    return cats


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"


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


def report(results: list[dict]) -> None:
    identical = [r for r in results if not r["diff"]]
    different = [r for r in results if r["diff"]]

    print(f"\n{BOLD}=== Round-trip consistency check ==={RESET}")
    print(
        f"Total: {len(results)}  Identical: {len(identical)}  Different: {len(different)}\n"
    )

    if identical:
        print(f"{GREEN}✓ Identical ({len(identical)}){RESET}")
        for r in identical:
            print(f"  {r['article_id']}  {r['title'][:60]}")

    if different:
        print(f"\n{RED}✗ Different ({len(different)}){RESET}")
        for r in different:
            cats = categorise(r["diff"])
            cat_str = ", ".join(sorted(cats)) if cats else "other"
            added = sum(
                1 for l in r["diff"] if l.startswith("+") and not l.startswith("+++")
            )
            removed = sum(
                1 for l in r["diff"] if l.startswith("-") and not l.startswith("---")
            )
            print(
                f"\n{BOLD}{r['article_id']}  {r['title'][:60]}{RESET}"
                f"  [{cat_str}]  +{added}/-{removed} lines"
            )
            # Show up to 80 diff lines to keep output manageable
            shown = r["diff"][:80]
            print(colour_diff(shown))
            if len(r["diff"]) > 80:
                print(
                    f"  {YELLOW}... {len(r['diff']) - 80} more lines truncated{RESET}"
                )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between requests (default 1.5)",
    )
    p.add_argument("--article-id", default="", help="Check only this article id")
    return p


def main() -> None:
    args = build_parser().parse_args()

    client = ZhihuClient.from_env_or_cache(allow_login=False)

    # Collect articles to check
    if args.article_id:
        md_path = ARTICLE_DIR / args.article_id / "index.md"
        if not md_path.exists():
            print(f"Not found: {md_path}", file=sys.stderr)
            sys.exit(1)
        candidates = [(args.article_id, md_path)]
    else:
        candidates = []
        for d in sorted(ARTICLE_DIR.iterdir()):
            if not d.is_dir():
                continue
            md = d / "index.md"
            if not md.exists():
                continue
            meta, _ = read_markdown_document(md)
            aid = str(meta.get("zhihu_article_id", "")).strip()
            if not aid:
                aid = d.name  # directory name is the article id
            candidates.append((aid, md))

    results: list[dict] = []
    for i, (aid, md_path) in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] Checking {aid} ...", end=" ", flush=True)
        try:
            result = check_article(client, aid, md_path, args.delay)
            status = "OK" if not result["diff"] else f"{len(result['diff'])} diff lines"
            print(status)
            results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(
                {
                    "article_id": aid,
                    "title": md_path.parent.name,
                    "diff": [f"ERROR: {e}"],
                    "local_lines": [],
                    "rt_lines": [],
                }
            )

    report(results)


if __name__ == "__main__":
    main()
