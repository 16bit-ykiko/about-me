import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml

DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_FRONT_MATTER_KEYS = ("title", "description", "summary")
MARKDOWN_SUFFIXES = {".md", ".markdown"}
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_API_VERSION = "v1beta"
DEFAULT_INCLUDE_THOUGHTS = False
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_MAX_RETRIES = 3
MARKDOWN_SYSTEM_INSTRUCTION = """
You are an expert technical translator. Translate the user's Markdown into the target language.
Preserve Markdown structure, headings, list structure, block quotes, tables, and emphasis markers.
Do not add explanations. Do not wrap the answer in code fences.
Preserve URLs exactly. Preserve fenced code blocks, inline code, and code identifiers unless a human-language
comment inside code clearly needs translation.
""".strip()
TEXT_SYSTEM_INSTRUCTION = """
You are an expert bilingual translator. Translate the user's text into the target language naturally and accurately.
Return only the translated text without commentary.
""".strip()


def format_model_label(model: str) -> str:
    normalized = model.strip()
    if normalized == "gemini-2.5-pro":
        return "Gemini 2.5 Pro"
    return normalized


def build_english_ai_translation_notice(model: str) -> str:
    model_label = format_model_label(model)
    return (
        f"> This article was translated by AI using {model_label} from the original "
        "Chinese version. Minor inaccuracies may remain."
    )


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


def prepend_notice(body: str, notice: str) -> str:
    normalized_body = body.lstrip("\n")
    if normalized_body.startswith(notice):
        return normalized_body
    return f"{notice}\n\n{normalized_body}"


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
        self.api_key = resolved_key
        self.base_url = (
            os.environ.get("GOOGLE_GEMINI_BASE_URL", "").strip() or DEFAULT_BASE_URL
        ).rstrip("/")
        self.api_version = (
            os.environ.get("GOOGLE_GEMINI_API_VERSION", "").strip()
            or DEFAULT_API_VERSION
        )
        thinking_budget = os.environ.get("GOOGLE_GEMINI_THINKING_BUDGET", "").strip()
        self.thinking_budget = int(thinking_budget) if thinking_budget else None
        include_thoughts = os.environ.get("GOOGLE_GEMINI_INCLUDE_THOUGHTS", "").strip()
        self.include_thoughts = (
            include_thoughts.lower() in {"1", "true", "yes", "on"}
            if include_thoughts
            else DEFAULT_INCLUDE_THOUGHTS
        )
        timeout_seconds = os.environ.get("GOOGLE_GEMINI_TIMEOUT_SECONDS", "").strip()
        self.timeout_seconds = (
            int(timeout_seconds) if timeout_seconds else DEFAULT_TIMEOUT_SECONDS
        )
        max_retries = os.environ.get("GOOGLE_GEMINI_MAX_RETRIES", "").strip()
        self.max_retries = int(max_retries) if max_retries else DEFAULT_MAX_RETRIES
        self.model = model
        self.temperature = temperature

    def _build_endpoint(self) -> str:
        return f"{self.base_url}/{self.api_version}/models/{self.model}:generateContent"

    def _generate(self, prompt: str, *, system_instruction: str) -> str:
        generation_config: dict[str, Any] = {
            "temperature": self.temperature,
            "thinkingConfig": {
                "includeThoughts": self.include_thoughts,
            },
        }
        if self.thinking_budget is not None:
            generation_config["thinkingConfig"]["thinkingBudget"] = self.thinking_budget
        last_error: Exception | None = None
        response: requests.Response | None = None
        for attempt in range(1, self.max_retries + 1):
            print(
                f"[gemini] request model={self.model} attempt={attempt}/{self.max_retries}",
                flush=True,
            )
            try:
                response = requests.post(
                    self._build_endpoint(),
                    headers={
                        "x-goog-api-key": self.api_key,
                        "content-type": "application/json",
                    },
                    json={
                        "generationConfig": generation_config,
                        "systemInstruction": {
                            "parts": [{"text": system_instruction}],
                        },
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": prompt}],
                            }
                        ],
                    },
                    timeout=self.timeout_seconds,
                )
                if response.ok:
                    break
                if response.status_code not in {408, 429, 500, 502, 503, 504}:
                    raise RuntimeError(
                        f"Gemini request failed with {response.status_code}: {response.text}"
                    )
                print(
                    f"[gemini] retryable status={response.status_code} model={self.model}",
                    flush=True,
                )
                last_error = RuntimeError(
                    f"Gemini request failed with {response.status_code}: {response.text}"
                )
            except requests.RequestException as exc:
                print(
                    f"[gemini] request error model={self.model}: {exc}",
                    flush=True,
                )
                last_error = exc

            if attempt == self.max_retries:
                if last_error is not None:
                    raise RuntimeError(
                        f"Gemini request failed after {self.max_retries} attempts: {last_error}"
                    ) from last_error
                raise RuntimeError("Gemini request failed without a response.")
            time.sleep(min(2**attempt, 10))

        if response is None or not response.ok:
            if last_error is not None:
                raise RuntimeError(
                    f"Gemini request failed after {self.max_retries} attempts: {last_error}"
                ) from last_error
            raise RuntimeError("Gemini request failed without a response.")

        payload = response.json()
        candidates = payload.get("candidates") or []
        parts = []
        if candidates:
            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise RuntimeError(f"Gemini returned an empty response: {payload}")
        return text

    def translate_text(self, text: str, options: TranslationOptions) -> str:
        if not text.strip():
            return text

        if options.markdown:
            prompt = (
                f"Source language: {options.source_lang}\n"
                f"Target language: {options.target_lang}\n\n"
                "Translate the following Markdown and return only the translated Markdown:\n\n"
                f"{text}"
            )
            return self._generate(
                prompt, system_instruction=MARKDOWN_SYSTEM_INSTRUCTION
            )

        prompt = (
            f"Source language: {options.source_lang}\n"
            f"Target language: {options.target_lang}\n\n"
            "Translate the following text:\n\n"
            f"{text}"
        )
        return self._generate(prompt, system_instruction=TEXT_SYSTEM_INSTRUCTION)

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
        if target_lang.strip().lower().startswith("english"):
            translated_body = prepend_notice(
                translated_body, build_english_ai_translation_notice(self.model)
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
