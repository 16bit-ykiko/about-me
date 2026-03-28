#!/usr/bin/env python3
"""
Chinese Markdown formatter / linter.

Usage:
  uv run python scripts/md_format.py [--fix] [files ...]
  uv run python scripts/md_format.py [--fix]          # all zh-cn articles

Modes:
  (default)  lint: report violations, exit 1 if any found
  --fix      fix:  auto-fix safe violations in-place, report lint-only issues
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTICLE_DIR = (
    Path(__file__).resolve().parent.parent
    / "website"
    / "content"
    / "zh-cn"
    / "articles"
)

# CJK ideograph ranges only — deliberately excludes CJK Symbols & Punctuation
# (\u3000-\u303f) so that 。，！？ etc. don't trigger spacing rules.
CJK_RE = re.compile(
    r"[\u3040-\u30ff"    # Hiragana + Katakana
    r"\u3400-\u4dbf"     # CJK Extension A
    r"\u4e00-\u9fff"     # CJK Unified Ideographs (main block)
    r"\uf900-\ufaff"     # CJK Compatibility Ideographs
    r"]"
)

# Single CJK char pattern for boundary checks
_CJK = (
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
)

# Atomic ASCII term: letters/digits optionally linked by +, -, #, .
# Covers: C++17, C#, x86-64, Node.js, ARMv8, Python3.12, etc.
_ASCII_ATOM = r"[A-Za-z0-9]+(?:[+\-#.][A-Za-z0-9]+)*[+#]*"

# Canonical noun map: wrong → correct (whole-word match in plain text)
NOUN_MAP: dict[str, str] = {
    "gcc": "GCC",
    "Gcc": "GCC",
    "clang": "Clang",
    "CLANG": "Clang",
    "msvc": "MSVC",
    "Msvc": "MSVC",
    "llvm": "LLVM",
    "Llvm": "LLVM",
    "cmake": "CMake",
    "Cmake": "CMake",
    "CMAKE": "CMake",
    "python": "Python",
    "PYTHON": "Python",
    "rust": "Rust",
    "RUST": "Rust",
    "c++": "C++",
    "CPP": "C++",
    "cpp": "C++",
    "cpu": "CPU",
    "Cpu": "CPU",
    "gpu": "GPU",
    "Gpu": "GPU",
    "abi": "ABI",
    "Abi": "ABI",
    "api": "API",
    "Api": "API",
    "elf": "ELF",
    "Elf": "ELF",
    "posix": "POSIX",
    "Posix": "POSIX",
    "github": "GitHub",
    "Github": "GitHub",
    "GITHUB": "GitHub",
    "linux": "Linux",
    "LINUX": "Linux",
    "windows": "Windows",
    "WINDOWS": "Windows",
    "macos": "macOS",
    "MacOS": "macOS",
    "MACOS": "macOS",
    "X86": "x86",
    "X86-64": "x86-64",
    "arm": "ARM",
    "Arm": "ARM",
}

# Chinese tech typos: wrong → correct
TYPO_MAP: dict[str, str] = {
    "登陆": "登录",
    "帐号": "账号",
    "联接": "连接",
    "其它": "其他",
    "粘帖": "粘贴",
    "搜寻": "搜索",
}

# Full-width digits/letters → half-width offset
_FW_DIGIT_START = 0xFF10   # ０
_FW_UPPER_START = 0xFF21   # Ａ
_FW_LOWER_START = 0xFF41   # ａ


# ---------------------------------------------------------------------------
# Inline tokeniser
# ---------------------------------------------------------------------------

@dataclass
class Span:
    """A segment of a source line."""
    kind: str    # "text" | "code" | "link" | "image" | "url" | "md_syntax"
    text: str    # raw source text of this span
    inner: str = ""  # for link/image: the alt/label text; for code: content


# Tokenise a single source line into Spans.
# Regions: inline code `...`, links [label](url), images ![alt](url),
# bold/italic markers (**/*), everything else is "text".
_INLINE_RE = re.compile(
    r"(`+)(.+?)\1"                              # inline code
    r"|!\[([^\]]*)\]\(([^)]*)\)"                # image ![alt](url)
    r"|\[([^\]]*)\]\(([^)]*)\)"                 # link [label](url)
    r"|(\*{1,3}|_{1,3})"                        # bold/italic marker
    r"|(\\[\S])"                                 # escape sequence
    ,
    re.DOTALL,
)


def tokenise(line: str) -> list[Span]:
    spans: list[Span] = []
    pos = 0
    for m in _INLINE_RE.finditer(line):
        if m.start() > pos:
            spans.append(Span("text", line[pos:m.start()]))
        if m.group(1):  # inline code
            spans.append(Span("code", m.group(0), inner=m.group(2)))
        elif m.group(3) is not None:  # image
            spans.append(Span("image", m.group(0), inner=m.group(3)))
        elif m.group(5) is not None:  # link
            spans.append(Span("link", m.group(0), inner=m.group(5)))
        elif m.group(7):  # bold/italic marker
            spans.append(Span("md_syntax", m.group(0)))
        elif m.group(8):  # escape
            spans.append(Span("text", m.group(0)))
        pos = m.end()
    if pos < len(line):
        spans.append(Span("text", line[pos:]))
    return spans


# ---------------------------------------------------------------------------
# Issue dataclass
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    line_no: int
    rule: str
    message: str
    fixable: bool = True


# ---------------------------------------------------------------------------
# Per-line rule functions
# Each returns (fixed_line, list[Issue]).
# They operate on the full raw line; block-level skipping is done upstream.
# ---------------------------------------------------------------------------

def _is_cjk(ch: str) -> bool:
    return bool(CJK_RE.match(ch))


def _is_ascii_alnum(ch: str) -> bool:
    return ch.isascii() and (ch.isalpha() or ch.isdigit())


def fix_fullwidth(line: str, lno: int) -> tuple[str, list[Issue]]:
    """Convert full-width digits/letters to half-width."""
    issues: list[Issue] = []
    out = []
    for ch in line:
        cp = ord(ch)
        if _FW_DIGIT_START <= cp <= _FW_DIGIT_START + 9:
            out.append(chr(cp - _FW_DIGIT_START + ord("0")))
            issues.append(Issue(lno, "fullwidth", f"全角字符「{ch}」→半角", fixable=True))
        elif _FW_UPPER_START <= cp <= _FW_UPPER_START + 25:
            out.append(chr(cp - _FW_UPPER_START + ord("A")))
            issues.append(Issue(lno, "fullwidth", f"全角字符「{ch}」→半角", fixable=True))
        elif _FW_LOWER_START <= cp <= _FW_LOWER_START + 25:
            out.append(chr(cp - _FW_LOWER_START + ord("a")))
            issues.append(Issue(lno, "fullwidth", f"全角字符「{ch}」→半角", fixable=True))
        else:
            out.append(ch)
    return "".join(out), issues


def fix_spacing_text(text: str, lno: int) -> tuple[str, list[Issue]]:
    """
    Insert spaces at CJK↔ASCII boundaries within a plain-text segment.
    The caller is responsible for NOT passing code/url segments.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues

    # Tokenise text into atomic ASCII terms and CJK/other chars
    atoms: list[str] = []
    pos = 0
    for m in re.finditer(_ASCII_ATOM, text):
        if m.start() > pos:
            atoms.extend(list(text[pos:m.start()]))
        atoms.append(m.group(0))
        pos = m.end()
    if pos < len(text):
        atoms.extend(list(text[pos:]))

    out = []
    for i, tok in enumerate(atoms):
        if i > 0:
            prev = atoms[i - 1]
            prev_last = prev[-1]
            cur_first = tok[0]
            need_space = (
                (_is_cjk(prev_last) and _is_ascii_alnum(cur_first))
                or (_is_ascii_alnum(prev_last) and _is_cjk(cur_first))
            )
            if need_space:
                if out and out[-1] != " ":
                    issues.append(Issue(
                        lno, "spacing",
                        f"缺少空格：「{prev_last}{cur_first}」→「{prev_last} {cur_first}」",
                        fixable=True,
                    ))
                    out.append(" ")
        out.append(tok)
    return "".join(out), issues


def fix_spacing_boundary(
    spans: list[Span], lno: int
) -> tuple[list[Span], list[Issue]]:
    """
    Insert spaces at boundaries between text/code/link/image spans and CJK text.
    Only checks the outermost char of each span so there's no overlap with
    fix_spacing_text (which handles CJK↔ASCII within a single text span).
    """
    issues: list[Issue] = []

    def last_nonspace(s: Span) -> str:
        return s.text.rstrip()[-1] if s.text.rstrip() else ""

    def first_nonspace(s: Span) -> str:
        return s.text.lstrip()[0] if s.text.lstrip() else ""

    result: list[Span] = []
    for i, span in enumerate(spans):
        if i > 0 and result:
            prev = result[-1]
            # Only check boundaries that cross a span-type change
            if prev.kind == "text" and span.kind in ("code", "link", "image"):
                lc = last_nonspace(prev)
                if lc and _is_cjk(lc) and not prev.text.endswith(" "):
                    issues.append(Issue(
                        lno, "spacing",
                        f"「{lc}」与 {span.kind} 之间缺少空格",
                        fixable=True,
                    ))
                    result.append(Span("text", " "))
            elif prev.kind in ("code", "link", "image") and span.kind == "text":
                fc = first_nonspace(span)
                if fc and _is_cjk(fc) and not span.text.startswith(" "):
                    issues.append(Issue(
                        lno, "spacing",
                        f"{prev.kind} 与「{fc}」之间缺少空格",
                        fixable=True,
                    ))
                    result.append(Span("text", " "))
        result.append(span)
    return result, issues


def fix_nouns(text: str, lno: int) -> tuple[str, list[Issue]]:
    """Fix canonical noun capitalisation in plain text."""
    issues: list[Issue] = []
    # Sorted by length descending so longer matches win
    for wrong, correct in sorted(NOUN_MAP.items(), key=lambda x: -len(x[0])):
        pattern = re.compile(r"(?<![A-Za-z0-9+#])" + re.escape(wrong) + r"(?![A-Za-z0-9+#])")
        def _repl(m: re.Match, c: str = correct, w: str = wrong, l: int = lno) -> str:
            issues.append(Issue(l, "noun", f"「{w}」→「{c}」", fixable=True))
            return c
        text = pattern.sub(_repl, text)
    return text, issues


def fix_typos(text: str, lno: int) -> tuple[str, list[Issue]]:
    """Fix common Chinese tech typos."""
    issues: list[Issue] = []
    for wrong, correct in TYPO_MAP.items():
        if wrong in text:
            count = text.count(wrong)
            text = text.replace(wrong, correct)
            for _ in range(count):
                issues.append(Issue(lno, "typo", f"「{wrong}」→「{correct}」", fixable=True))
    return text, issues


def fix_ellipsis_dash(text: str, lno: int) -> tuple[str, list[Issue]]:
    """Replace ... with …… and -- with —— in CJK context."""
    issues: list[Issue] = []
    # ... → …… only when adjacent to CJK or at start/end of segment
    def _ellipsis_repl(m: re.Match) -> str:
        before = text[:m.start()]
        after = text[m.end():]
        if (before and _is_cjk(before[-1])) or (after and _is_cjk(after[0])):
            issues.append(Issue(lno, "punct", "「...」→「……」", fixable=True))
            return "\u2026\u2026"
        return m.group(0)
    text = re.sub(r"\.{3}", _ellipsis_repl, text)

    # -- → —— only when adjacent to CJK
    def _dash_repl(m: re.Match) -> str:
        before = text[:m.start()]
        after = text[m.end():]
        if (before and _is_cjk(before[-1])) or (after and _is_cjk(after[0])):
            issues.append(Issue(lno, "punct", "「--」→「——」", fixable=True))
            return "\u2014\u2014"
        return m.group(0)
    text = re.sub(r"--(?!-)", _dash_repl, text)
    return text, issues


def fix_dup_punct(text: str, lno: int) -> tuple[str, list[Issue]]:
    """Collapse repeated stop/pause punctuation (not tone marks like ！？)."""
    issues: list[Issue] = []
    STOP = r"[，。；：,\.;:]"
    def _repl(m: re.Match) -> str:
        issues.append(Issue(lno, "punct", f"重复标点「{m.group(0)}」→「{m.group(1)}」", fixable=True))
        return m.group(1)
    # Don't collapse …… (U+2026 U+2026) or —— (U+2014 U+2014)
    text = re.sub(r"(" + STOP + r")\1+", _repl, text)
    return text, issues


def fix_number_unit(text: str, lno: int) -> tuple[str, list[Issue]]:
    """
    Insert space between number and letter unit (8GB → 8 GB).
    Only triggers for known multi-char units or well-known single-char units
    (B, K, M, G, T) to avoid false positives like '2w' (万) or '3d' (day slang).
    Remove space between number and %, °.
    """
    issues: list[Issue] = []
    # Require unit to be either 2+ chars, or exactly one of the known SI/storage letters
    KNOWN_SINGLE = r"[BKMGT]"   # uppercase only for single-char units
    _UNIT_RE = re.compile(r"(\d)([A-Za-z]{2,}|" + KNOWN_SINGLE + r")(?![+\-#.A-Za-z])")

    def _unit_repl(m: re.Match) -> str:
        issues.append(Issue(lno, "spacing", f"「{m.group(0)}」→「{m.group(1)} {m.group(2)}」", fixable=True))
        return m.group(1) + " " + m.group(2)
    text = _UNIT_RE.sub(_unit_repl, text)

    # Remove space before % and °
    def _pct_repl(m: re.Match) -> str:
        if m.group(1):  # had a space
            issues.append(Issue(lno, "spacing", f"「{m.group(0).strip()}」前不应有空格", fixable=True))
        return m.group(2)
    text = re.sub(r"(\s?)([%°])", _pct_repl, text)
    return text, issues


def fix_quotes(text: str, lno: int) -> tuple[str, list[Issue]]:
    """Replace curved quotes with corner quotes in CJK context."""
    issues: list[Issue] = []
    # Simple heuristic: if the surrounding text contains CJK, convert.
    if not CJK_RE.search(text):
        return text, issues
    # Match paired "..." → 「...」
    def _dq(m: re.Match) -> str:
        issues.append(Issue(lno, "quote", '「」替换弯引号', fixable=True))
        return "\u300c" + m.group(1) + "\u300d"
    text = re.sub(r"\u201c([^\u201d]*)\u201d", _dq, text)  # " "
    # Match paired '...' → 『...』
    def _sq(m: re.Match) -> str:
        issues.append(Issue(lno, "quote", "『』替换弯引号", fixable=True))
        return "\u300e" + m.group(1) + "\u300f"
    text = re.sub(r"\u2018([^\u2019]*)\u2019", _sq, text)  # ' '
    return text, issues


def lint_punct_ascii(text: str, lno: int) -> list[Issue]:
    """Lint: ASCII punctuation after ASCII word/code in CJK context (lint only)."""
    issues: list[Issue] = []
    if not CJK_RE.search(text):
        return issues
    for m in re.finditer(r"([A-Za-z`])[,\.!?:;](\s|$)", text):
        # Skip if this looks like a list item marker at start (e.g. "1. " already handled)
        ctx = text[:m.start()].lstrip()
        if not ctx:  # at start of (stripped) segment, likely a list marker
            continue
        issues.append(Issue(lno, "punct",
            f"中文语境下「{m.group(0).strip()}」后应用中文标点",
            fixable=False))
    return issues


def fix_heading_space(line: str, lno: int) -> tuple[str, list[Issue]]:
    """Ensure exactly one space after # in headings."""
    m = re.match(r"^(#{1,6})(\s*)(.*)", line)
    if not m:
        return line, []
    hashes, spaces, rest = m.group(1), m.group(2), m.group(3)
    if spaces != " ":
        return hashes + " " + rest, [Issue(lno, "structure", f"标题「#」后应有且仅有一个空格", fixable=True)]
    return line, []


def fix_list_space(line: str, lno: int) -> tuple[str, list[Issue]]:
    """Ensure exactly one space after list markers."""
    m = re.match(r"^(\s*)([-*+]|(\d+)\.)(\S)", line)
    if not m:
        return line, []
    return line[:m.start(4)] + " " + line[m.start(4):], [
        Issue(lno, "structure", "列表标记符后缺少空格", fixable=True)
    ]


def lint_code_block_lang(fence: str, lno: int) -> list[Issue]:
    """Lint: fenced code block must have a language identifier."""
    m = re.match(r"^(`{3,}|~{3,})\s*$", fence)
    if m:
        return [Issue(lno, "code_block", "代码块未声明语言（如 ```python）", fixable=False)]
    return []


# ---------------------------------------------------------------------------
# Process a single file
# ---------------------------------------------------------------------------

@dataclass
class FileResult:
    path: Path
    issues: list[Issue] = field(default_factory=list)
    fixed_lines: list[str] | None = None  # None in lint-only mode


def process_file(path: Path, fix: bool) -> FileResult:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    result = FileResult(path=path)
    out_lines: list[str] = []

    in_frontmatter = False
    frontmatter_done = False
    in_code_block = False
    code_fence: str = ""

    for lno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n").rstrip("\r")
        suffix = raw_line[len(line):]  # original line ending

        # ---- Block-level state ----

        # Frontmatter
        if lno == 1 and line.strip() == "---":
            in_frontmatter = True
            out_lines.append(raw_line)
            continue
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
                frontmatter_done = True
            out_lines.append(raw_line)
            continue

        # Fenced code block
        fence_m = re.match(r"^(`{3,}|~{3,})", line)
        if fence_m:
            if not in_code_block:
                in_code_block = True
                code_fence = fence_m.group(1)
                result.issues.extend(lint_code_block_lang(line, lno))
            elif line.startswith(code_fence):
                in_code_block = False
                code_fence = ""
            out_lines.append(raw_line)
            continue

        if in_code_block:
            out_lines.append(raw_line)
            continue

        # ---- Line-level transformations ----

        # Heading
        if re.match(r"^#{1,6}\s", line) or re.match(r"^#{1,6}[^\s#]", line):
            line, iss = fix_heading_space(line, lno)
            result.issues.extend(iss)

        # List marker
        if re.match(r"^\s*[-*+]\S", line) or re.match(r"^\s*\d+\.\S", line):
            line, iss = fix_list_space(line, lno)
            result.issues.extend(iss)

        # Full-width → half-width (always fixable, apply early)
        line, iss = fix_fullwidth(line, lno)
        result.issues.extend(iss)

        # Tokenise inline spans
        spans = tokenise(line)

        # Apply spacing fix at span boundaries
        spans, iss = fix_spacing_boundary(spans, lno)
        result.issues.extend(iss)

        # Apply text-level fixes to each "text", link inner, image inner
        new_spans: list[Span] = []
        for span in spans:
            if span.kind == "text":
                t, iss = fix_spacing_text(span.text, lno)
                result.issues.extend(iss)
                t, iss = fix_nouns(t, lno)
                result.issues.extend(iss)
                t, iss = fix_typos(t, lno)
                result.issues.extend(iss)
                t, iss = fix_ellipsis_dash(t, lno)
                result.issues.extend(iss)
                t, iss = fix_dup_punct(t, lno)
                result.issues.extend(iss)
                t, iss = fix_number_unit(t, lno)
                result.issues.extend(iss)
                t, iss = fix_quotes(t, lno)
                result.issues.extend(iss)
                result.issues.extend(lint_punct_ascii(t, lno))
                new_spans.append(Span("text", t))
            elif span.kind in ("link", "image"):
                # Fix the inner label text
                inner = span.inner
                inner, iss = fix_spacing_text(inner, lno)
                result.issues.extend(iss)
                inner, iss = fix_nouns(inner, lno)
                result.issues.extend(iss)
                # Rebuild the span text with fixed inner
                if span.kind == "link":
                    # [label](url) — replace label part
                    new_text = re.sub(
                        r"^\[([^\]]*)\]",
                        "[" + inner.replace("\\", "\\\\") + "]",
                        span.text,
                        count=1,
                    )
                else:
                    new_text = re.sub(
                        r"^!\[([^\]]*)\]",
                        "![" + inner.replace("\\", "\\\\") + "]",
                        span.text,
                        count=1,
                    )
                new_spans.append(Span(span.kind, new_text, inner=inner))
            else:
                new_spans.append(span)

        line = "".join(s.text for s in new_spans)
        out_lines.append(line + suffix)

    # File-level: EOF newline
    if out_lines and not out_lines[-1].endswith("\n"):
        result.issues.append(Issue(len(lines), "structure", "文件末尾缺少换行符", fixable=True))
        out_lines[-1] = out_lines[-1] + "\n"

    # Consecutive blank lines
    compressed: list[str] = []
    blank_count = 0
    for raw in out_lines:
        if raw.strip() == "":
            blank_count += 1
            if blank_count > 1:
                result.issues.append(Issue(0, "structure", "连续空行已压缩", fixable=True))
                continue
        else:
            blank_count = 0
        compressed.append(raw)

    if fix:
        result.fixed_lines = compressed

    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

RESET = "\033[0m"
RED   = "\033[31m"
GREEN = "\033[32m"
YELLOW= "\033[33m"
CYAN  = "\033[36m"
BOLD  = "\033[1m"


def report(results: list[FileResult], fix: bool) -> None:
    total_issues = sum(len(r.issues) for r in results)
    fixable = sum(sum(1 for i in r.issues if i.fixable) for r in results)
    lint_only = total_issues - fixable

    print(f"\n{BOLD}=== md_format ==={RESET}")
    mode = "fix" if fix else "lint"
    print(f"Mode: {mode}  Files: {len(results)}  Issues: {total_issues}  "
          f"(auto-fixed: {fixable if fix else 0}  lint-only: {lint_only})\n")

    for r in results:
        if not r.issues:
            print(f"{GREEN}✓{RESET} {r.path}")
            continue
        fixable_count = sum(1 for i in r.issues if i.fixable)
        lintonly_count = len(r.issues) - fixable_count
        print(f"{RED}✗{RESET} {r.path}  "
              f"({fixable_count} fixable, {lintonly_count} lint-only)")
        for issue in r.issues:
            color = YELLOW if not issue.fixable else (GREEN if fix else RED)
            tag = f"[{issue.rule}]"
            ln = f":{issue.line_no}" if issue.line_no else ""
            print(f"  {color}{tag}{RESET}{ln} {issue.message}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fix", action="store_true", help="Auto-fix safe violations in-place")
    p.add_argument("files", nargs="*", help="Markdown files to check (default: all zh-cn articles)")
    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        paths = sorted(ARTICLE_DIR.glob("*/index.md"))

    if not paths:
        print("No files found.", file=sys.stderr)
        sys.exit(1)

    results: list[FileResult] = []
    for path in paths:
        result = process_file(path, fix=args.fix)
        results.append(result)
        if args.fix and result.fixed_lines is not None:
            path.write_text("".join(result.fixed_lines), encoding="utf-8")

    report(results, fix=args.fix)

    lint_only_issues = sum(
        sum(1 for i in r.issues if not i.fixable) for r in results
    )
    if lint_only_issues > 0 or (not args.fix and any(r.issues for r in results)):
        sys.exit(1)


if __name__ == "__main__":
    main()
