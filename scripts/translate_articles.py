import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rewrite_en_article_links import collect_article_ids, rewrite_article_links
from translate import GeminiTranslator, extract_front_matter, render_front_matter

_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
_TZ_NEW_YORK = ZoneInfo("America/New_York")
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def convert_dates_to_new_york(markdown_text: str) -> str:
    metadata, body, has_front_matter = extract_front_matter(markdown_text)
    if not has_front_matter:
        return markdown_text
    changed = False
    for key in ("date", "updated"):
        value = metadata.get(key)
        if not isinstance(value, str):
            continue
        try:
            dt = datetime.strptime(value, _DATE_FMT).replace(tzinfo=_TZ_SHANGHAI)
            metadata[key] = dt.astimezone(_TZ_NEW_YORK).strftime(_DATE_FMT)
            changed = True
        except ValueError:
            pass
    if not changed:
        return markdown_text
    return render_front_matter(metadata, body)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "website/content/zh-cn/articles"
DEFAULT_TARGET_ROOT = REPO_ROOT / "website/content/en/articles"
DEFAULT_WORKERS = 8
ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class FileChange:
    action: str
    relative_path: Path


def run_git_diff(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def normalize_path(path_text: str, source_root: Path) -> Path | None:
    source_root_relative = source_root.relative_to(REPO_ROOT)
    path = Path(path_text)
    try:
        return path.relative_to(source_root_relative)
    except ValueError:
        return None


def parse_name_status(lines: list[str], source_root: Path) -> list[FileChange]:
    changes: list[FileChange] = []
    for line in lines:
        fields = line.split("\t")
        status = fields[0]
        kind = status[0]
        if kind == "R":
            old_path = normalize_path(fields[1], source_root)
            new_path = normalize_path(fields[2], source_root)
            if old_path is not None:
                changes.append(FileChange(action="delete", relative_path=old_path))
            if new_path is not None:
                changes.append(FileChange(action="upsert", relative_path=new_path))
            continue
        if kind == "C":
            new_path = normalize_path(fields[2], source_root)
            if new_path is not None:
                changes.append(FileChange(action="upsert", relative_path=new_path))
            continue

        path = normalize_path(fields[1], source_root)
        if path is None:
            continue
        action = "delete" if kind == "D" else "upsert"
        changes.append(FileChange(action=action, relative_path=path))
    return changes


def collect_changes(source_root: Path, base_ref: str) -> list[FileChange]:
    all_changes: dict[tuple[str, str], FileChange] = {}
    source_root_relative = str(source_root.relative_to(REPO_ROOT))

    if base_ref and base_ref != ZERO_SHA:
        for change in parse_name_status(
            run_git_diff(f"{base_ref}...HEAD", "--", source_root_relative),
            source_root,
        ):
            all_changes[(change.action, change.relative_path.as_posix())] = change

    for change in parse_name_status(
        run_git_diff("--", source_root_relative), source_root
    ):
        all_changes[(change.action, change.relative_path.as_posix())] = change

    return list(all_changes.values())


def collect_all_changes(source_root: Path) -> list[FileChange]:
    changes: list[FileChange] = []
    for path in sorted(source_root.rglob("*")):
        if path.is_file():
            changes.append(FileChange("upsert", path.relative_to(source_root)))
    return changes


def prune_empty_directories(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def sync_asset(change: FileChange, source_root: Path, target_root: Path) -> None:
    source_path = source_root / change.relative_path
    target_path = target_root / change.relative_path

    if change.action == "delete":
        if target_path.exists():
            target_path.unlink()
            prune_empty_directories(target_path.parent, target_root)
        return

    if not source_path.exists():
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    print(f"copied asset: {change.relative_path.as_posix()}", flush=True)


def translate_markdown_files(
    relative_paths: list[Path],
    source_root: Path,
    target_root: Path,
    *,
    source_lang: str,
    target_lang: str,
    model: str,
    temperature: float,
    workers: int,
    dry_run: bool,
) -> None:
    if not relative_paths:
        return

    total = len(relative_paths)
    if dry_run:
        for index, relative_path in enumerate(sorted(relative_paths), start=1):
            target_path = target_root / relative_path
            print(
                f"[dry-run {index}/{total}] translate {relative_path.as_posix()} -> {target_path.relative_to(REPO_ROOT).as_posix()}",
                flush=True,
            )
        return

    known_article_ids = collect_article_ids(source_root)

    def translate_one(index: int, relative_path: Path) -> str:
        source_path = source_root / relative_path
        target_path = target_root / relative_path
        started_at = time.monotonic()
        print(
            f"[start {index}/{total}] translating {relative_path.as_posix()}",
            flush=True,
        )
        translator = GeminiTranslator(model=model, temperature=temperature)
        markdown_text = source_path.read_text(encoding="utf-8")
        translated = translator.translate_markdown_document(
            markdown_text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        if target_lang.strip().lower().startswith("english"):
            translated, rewritten_links = rewrite_article_links(
                translated, known_article_ids
            )
            translated = convert_dates_to_new_york(translated)
        else:
            rewritten_links = 0
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(translated, encoding="utf-8")
        elapsed = time.monotonic() - started_at
        return (
            f"[done {index}/{total}] translated {relative_path.as_posix()} -> "
            f"{target_path.relative_to(REPO_ROOT).as_posix()} "
            f"(rewrote {rewritten_links} links, {elapsed:.1f}s)"
        )

    failures: list[str] = []
    sorted_paths = sorted(relative_paths)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {
            executor.submit(translate_one, index, relative_path): (index, relative_path)
            for index, relative_path in enumerate(sorted_paths, start=1)
        }
        for future in as_completed(future_map):
            index, relative_path = future_map[future]
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                message = f"[fail {index}/{total}] {relative_path.as_posix()}: {exc}"
                failures.append(message)
                print(message, flush=True)

    if failures:
        raise RuntimeError(
            "One or more article translations failed:\n" + "\n".join(failures)
        )


def delete_markdown_files(relative_paths: list[Path], target_root: Path) -> None:
    for relative_path in sorted(relative_paths):
        target_path = target_root / relative_path
        if not target_path.exists():
            continue
        target_path.unlink()
        prune_empty_directories(target_path.parent, target_root)
        print(f"deleted translation: {relative_path.as_posix()}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="translate_articles.py",
        description="Incrementally translate changed zh-cn articles into en articles.",
    )
    parser.add_argument(
        "--base-ref", default="", help="Git base ref for committed diffs."
    )
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_SOURCE_ROOT),
        help="Source articles root. Default: website/content/zh-cn/articles",
    )
    parser.add_argument(
        "--target-root",
        default=str(DEFAULT_TARGET_ROOT),
        help="Target articles root. Default: website/content/en/articles",
    )
    parser.add_argument("--source-lang", default="zh-CN", help="Source language.")
    parser.add_argument("--target-lang", default="English", help="Target language.")
    parser.add_argument(
        "--model",
        default="gemini-2.5-pro",
        help="Gemini model name.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Translate all source articles instead of using git diff.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned work without writing files or calling Gemini.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Article translation concurrency. Default: {DEFAULT_WORKERS}.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    target_root = Path(args.target_root).expanduser().resolve()

    if args.all:
        changes = collect_all_changes(source_root)
    else:
        changes = collect_changes(source_root, args.base_ref.strip())

    if not changes:
        print("No article changes to translate.", flush=True)
        return

    markdown_to_translate: set[Path] = set()
    markdown_to_delete: set[Path] = set()

    for change in changes:
        if change.relative_path.name == "index.md":
            if change.action == "delete":
                markdown_to_delete.add(change.relative_path)
            else:
                markdown_to_translate.add(change.relative_path)
            continue

        if args.dry_run:
            print(
                f"[dry-run] {change.action} asset {change.relative_path.as_posix()}",
                flush=True,
            )
            continue
        sync_asset(change, source_root, target_root)

    delete_markdown_files(sorted(markdown_to_delete), target_root)
    translate_markdown_files(
        sorted(markdown_to_translate),
        source_root,
        target_root,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        model=args.model,
        temperature=args.temperature,
        workers=args.workers,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
