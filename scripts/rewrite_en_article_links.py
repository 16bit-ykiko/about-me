import argparse
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EN_ROOT = REPO_ROOT / "website/content/en/articles"
DEFAULT_ZH_ROOT = REPO_ROOT / "website/content/zh-cn/articles"
ARTICLE_LINK_PATTERN = re.compile(
    r"(?P<prefix>https://www\.ykiko\.me|https://ykiko\.me|)"
    r"/zh-cn/articles/(?P<article_id>\d+)(?P<suffix>/?(?:[?#][^\s)\"'>]*)?)"
)


def collect_article_ids(root: Path) -> set[str]:
    article_ids: set[str] = set()
    if not root.exists():
        return article_ids
    for article_dir in root.iterdir():
        if article_dir.is_dir() and (article_dir / "index.md").exists():
            article_ids.add(article_dir.name)
    return article_ids


def rewrite_article_links(text: str, article_ids: set[str]) -> tuple[str, int]:
    replacements = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replacements
        article_id = match.group("article_id")
        if article_id not in article_ids:
            return match.group(0)
        prefix = match.group("prefix")
        suffix = match.group("suffix")
        replacements += 1
        return f"{prefix}/en/articles/{article_id}{suffix}"

    return ARTICLE_LINK_PATTERN.sub(replace, text), replacements


def rewrite_file(path: Path, article_ids: set[str]) -> int:
    original = path.read_text(encoding="utf-8")
    rewritten, replacements = rewrite_article_links(original, article_ids)
    if replacements:
        path.write_text(rewritten, encoding="utf-8")
    return replacements


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rewrite_en_article_links.py",
        description="Rewrite internal zh-cn article links in English articles to en links.",
    )
    parser.add_argument(
        "--en-root",
        default=str(DEFAULT_EN_ROOT),
        help="English articles root. Default: website/content/en/articles",
    )
    parser.add_argument(
        "--zh-root",
        default=str(DEFAULT_ZH_ROOT),
        help="Chinese articles root used to determine known article ids.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    en_root = Path(args.en_root).expanduser().resolve()
    zh_root = Path(args.zh_root).expanduser().resolve()
    article_ids = collect_article_ids(zh_root)

    updated_files = 0
    updated_links = 0
    for path in sorted(en_root.rglob("index.md")):
        replacements = rewrite_file(path, article_ids)
        if replacements:
            updated_files += 1
            updated_links += replacements
            print(
                f"rewrote {replacements} links in {path.relative_to(REPO_ROOT).as_posix()}",
                flush=True,
            )

    print(
        f"updated {updated_links} links across {updated_files} files",
        flush=True,
    )


if __name__ == "__main__":
    main()
