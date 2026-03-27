import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_FRONT_MATTER_KEYS = ("title", "description", "summary")
MARKDOWN_SUFFIXES = {".md", ".markdown"}


def extract_front_matter(markdown_text: str) -> tuple[dict[str, Any], str, bool]:
    if not markdown_text.startswith("---\n"):
        return {}, markdown_text, False

    try:
        end_index = markdown_text.index("\n---\n", 4)
    except ValueError:
        return {}, markdown_text, False

    header_text = markdown_text[4:end_index]
    rest = markdown_text[end_index + 5 :]
    metadata = yaml.safe_load(header_text) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Markdown front matter must be a YAML mapping.")
    return metadata, rest.lstrip("\n"), True


def render_front_matter(metadata: dict[str, Any], body: str) -> str:
    header = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
    normalized_body = body.lstrip("\n")
    return f"---\n{header}\n---\n\n{normalized_body}\n"


@dataclass(frozen=True)
class TranslationOptions:
    source_lang: str = "auto"
    target_lang: str = "English"
    model: str = DEFAULT_MODEL
    temperature: float = 0.2
    markdown: bool = False


class GeminiTranslator:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.2,
    ):
        resolved_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        if not resolved_key:
            raise RuntimeError("Missing GEMINI_API_KEY.")
        self.client = genai.Client(api_key=resolved_key)
        self.model = model
        self.temperature = temperature

    def _generate(self, prompt: str, *, system_instruction: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=self.temperature,
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text

    def translate_text(self, text: str, options: TranslationOptions) -> str:
        if not text.strip():
            return text

        if options.markdown:
            system_instruction = (
                "You are an expert technical translator. Translate the user's Markdown into the target language. "
                "Preserve Markdown structure, headings, list structure, block quotes, tables, and emphasis markers. "
                "Do not add explanations. Do not wrap the answer in code fences. "
                "Preserve URLs exactly. Preserve fenced code blocks, inline code, and code identifiers unless a human-language "
                "comment inside code clearly needs translation."
            )
            prompt = (
                f"Source language: {options.source_lang}\n"
                f"Target language: {options.target_lang}\n\n"
                "Translate the following Markdown and return only the translated Markdown:\n\n"
                f"{text}"
            )
            return self._generate(prompt, system_instruction=system_instruction)

        system_instruction = (
            "You are an expert bilingual translator. Translate the user's text into the target language naturally and accurately. "
            "Return only the translated text without commentary."
        )
        prompt = (
            f"Source language: {options.source_lang}\n"
            f"Target language: {options.target_lang}\n\n"
            "Translate the following text:\n\n"
            f"{text}"
        )
        return self._generate(prompt, system_instruction=system_instruction)

    def translate_value(self, value: Any, *, source_lang: str, target_lang: str) -> Any:
        if isinstance(value, str):
            return self.translate_text(
                value,
                TranslationOptions(
                    source_lang=source_lang,
                    target_lang=target_lang,
                    model=self.model,
                    temperature=self.temperature,
                    markdown=False,
                ),
            )
        if isinstance(value, list):
            translated_items: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    translated_items.append(
                        self.translate_text(
                            item,
                            TranslationOptions(
                                source_lang=source_lang,
                                target_lang=target_lang,
                                model=self.model,
                                temperature=self.temperature,
                                markdown=False,
                            ),
                        )
                    )
                else:
                    translated_items.append(item)
            return translated_items
        return value

    def translate_markdown_document(
        self,
        markdown_text: str,
        *,
        source_lang: str,
        target_lang: str,
        front_matter_keys: tuple[str, ...] = DEFAULT_FRONT_MATTER_KEYS,
    ) -> str:
        metadata, body, has_front_matter = extract_front_matter(markdown_text)
        translated_body = self.translate_text(
            body,
            TranslationOptions(
                source_lang=source_lang,
                target_lang=target_lang,
                model=self.model,
                temperature=self.temperature,
                markdown=True,
            ),
        )
        if not has_front_matter:
            return translated_body

        translated_metadata = dict(metadata)
        for key in front_matter_keys:
            if key in translated_metadata:
                translated_metadata[key] = self.translate_value(
                    translated_metadata[key],
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
        return render_front_matter(translated_metadata, translated_body)


def load_input(text: str | None, file_path: str) -> tuple[str, Path | None]:
    if file_path:
        path = Path(file_path).expanduser().resolve()
        return path.read_text(encoding="utf-8"), path
    if text is not None:
        return text, None
    if not sys.stdin.isatty():
        return sys.stdin.read(), None
    raise RuntimeError("Provide text, --file, or pipe content through stdin.")


def infer_markdown(path: Path | None, markdown_flag: bool) -> bool:
    if markdown_flag:
        return True
    if path is None:
        return False
    return path.suffix.lower() in MARKDOWN_SUFFIXES


def write_output(content: str, *, output_path: str, in_place_path: Path | None) -> None:
    if output_path:
        path = Path(output_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(path)
        return
    if in_place_path is not None:
        in_place_path.write_text(content, encoding="utf-8")
        print(in_place_path)
        return
    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="translate.py",
        description="Translate text or Markdown files with Gemini.",
        epilog=(
            "Examples:\n"
            '  uv run python scripts/translate.py "你好，世界" --target English\n'
            "  uv run python scripts/translate.py --file article.md --target English --markdown --output article.en.md\n"
            "  cat note.txt | uv run python scripts/translate.py --target zh-CN\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("text", nargs="?", help="Inline text to translate.")
    parser.add_argument("--file", default="", help="Input file path.")
    parser.add_argument(
        "--output", default="", help="Write translated content to this path."
    )
    parser.add_argument(
        "--in-place", action="store_true", help="Overwrite the input file."
    )
    parser.add_argument(
        "--source", default="auto", help="Source language. Default: auto."
    )
    parser.add_argument(
        "--target", default="English", help="Target language. Default: English."
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        help="Gemini model name.",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.2, help="Sampling temperature."
    )
    parser.add_argument(
        "--markdown", action="store_true", help="Force Markdown translation mode."
    )
    parser.add_argument(
        "--front-matter-key",
        action="append",
        default=[],
        help="Front matter key to translate for Markdown files. Can be repeated.",
    )
    parser.add_argument(
        "--no-front-matter",
        action="store_true",
        help="Do not translate front matter values, only the Markdown body.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    raw_input, input_path = load_input(args.text, args.file)
    if args.in_place and input_path is None:
        raise RuntimeError("--in-place requires --file.")
    if args.in_place and args.output:
        raise RuntimeError("--in-place cannot be combined with --output.")

    markdown_mode = infer_markdown(input_path, args.markdown)
    translator = GeminiTranslator(model=args.model, temperature=args.temperature)

    if markdown_mode:
        if args.no_front_matter:
            front_matter_keys: tuple[str, ...] = ()
        elif args.front_matter_key:
            front_matter_keys = tuple(args.front_matter_key)
        else:
            front_matter_keys = DEFAULT_FRONT_MATTER_KEYS
        translated = translator.translate_markdown_document(
            raw_input,
            source_lang=args.source,
            target_lang=args.target,
            front_matter_keys=front_matter_keys,
        )
    else:
        translated = translator.translate_text(
            raw_input,
            TranslationOptions(
                source_lang=args.source,
                target_lang=args.target,
                model=args.model,
                temperature=args.temperature,
                markdown=False,
            ),
        )

    write_output(
        translated,
        output_path=args.output,
        in_place_path=input_path if args.in_place else None,
    )


if __name__ == "__main__":
    main()
