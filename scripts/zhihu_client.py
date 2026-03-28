import os
import re
import shutil
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
from pathlib import Path
from typing import Any

import requests
import yaml

from zhihu_parser import Parser

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)
PAGE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.zhihu.com/",
}
API_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.zhihu.com/",
}
LOGIN_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.zhihu.com",
    "Referer": "https://www.zhihu.com/signin",
    "x-requested-with": "fetch",
    "content-type": "application/json;charset=UTF-8",
}
ZHUANLAN_HEADERS = {
    "authority": "zhuanlan.zhihu.com",
    "user-agent": USER_AGENT,
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "origin": "https://zhuanlan.zhihu.com",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://zhuanlan.zhihu.com/write",
    "x-requested-with": "fetch",
}
REQUEST_TIMEOUT_SECONDS = 20
COOKIE_DIR = Path(__file__).resolve().parent.parent / ".cookie"
COOKIE_FILE = COOKIE_DIR / "zhihu.yaml"
LEGACY_COOKIE_FILES = [
    COOKIE_DIR / "zhihu.json",
    COOKIE_DIR / "zhihu.txt",
]
COLUMN_REQUEST_URL = "https://zhuanlan.zhihu.com/column/request"
SELF_PROFILE_API = "https://www.zhihu.com/api/v4/me"
QRCODE_API = "https://www.zhihu.com/api/v3/account/api/login/qrcode"
CAPTCHA_V2_API = "https://www.zhihu.com/api/v3/oauth/captcha/v2?type=captcha_sign_in"
UDID_API = "https://www.zhihu.com/udid"
ZHUANLAN_API = "https://zhuanlan.zhihu.com/api/articles"


@dataclass
class ZhihuColumn:
    id: str
    title: str
    intro: str
    articles_count: int
    followers: int

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "ZhihuColumn":
        column = payload["column"] if "column" in payload else payload
        return cls(
            id=str(column["id"]),
            title=column["title"],
            intro=column.get("intro", ""),
            articles_count=int(column.get("articles_count", 0)),
            followers=int(column.get("followers", 0)),
        )


@dataclass
class ZhihuArticle:
    id: str
    title: str
    url: str
    created: int
    updated: int
    column_id: str | None
    column_title: str | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "ZhihuArticle":
        column = payload.get("column") or {}
        article_id = str(payload["id"])
        return cls(
            id=article_id,
            title=payload["title"],
            url=f"https://zhuanlan.zhihu.com/p/{article_id}",
            created=int(payload.get("created", payload.get("updated", 0))),
            updated=int(payload.get("updated", payload.get("created", 0))),
            column_id=str(column["id"]) if column.get("id") is not None else None,
            column_title=column.get("title"),
        )


def parse_cookie_header(cookie_text: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for pair in cookie_text.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def format_cookie_header(session: requests.Session) -> str:
    cookie_items: list[str] = []
    seen_names: set[str] = set()
    for cookie in session.cookies:
        if cookie.name in seen_names:
            continue
        seen_names.add(cookie.name)
        cookie_items.append(f"{cookie.name}={cookie.value}")
    return "; ".join(cookie_items)


def ensure_cookie_dir() -> None:
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def load_cookie_cache(cache_path: Path = COOKIE_FILE) -> str:
    if not cache_path.exists():
        for legacy_path in LEGACY_COOKIE_FILES:
            if legacy_path.exists():
                if legacy_path.suffix == ".txt":
                    return legacy_path.read_text(encoding="utf-8").strip()
                payload = yaml.safe_load(legacy_path.read_text(encoding="utf-8")) or {}
                return str(payload.get("cookie_header", "")).strip()
        return ""
    payload = yaml.safe_load(cache_path.read_text(encoding="utf-8")) or {}
    return str(payload.get("cookie_header", "")).strip()


def save_cookie_cache(
    session: requests.Session, cache_path: Path = COOKIE_FILE
) -> None:
    ensure_cookie_dir()
    payload = {
        "cookie_header": format_cookie_header(session),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    cache_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def save_cookie_header(cookie_header: str, cache_path: Path = COOKIE_FILE) -> None:
    session = requests.Session()
    session.cookies.update(parse_cookie_header(cookie_header))
    save_cookie_cache(session, cache_path)


def save_github_secret(secret_name: str, cookie_header: str) -> None:
    if not shutil.which("gh"):
        raise RuntimeError("`gh` is not installed.")
    subprocess.run(
        ["gh", "secret", "set", secret_name],
        input=cookie_header,
        text=True,
        check=True,
    )


def open_url(url: str) -> bool:
    for command in ("xdg-open", "open"):
        path = shutil.which(command)
        if path:
            try:
                subprocess.Popen(
                    [path, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True
            except Exception:
                pass
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def extract_front_matter(markdown_text: str) -> tuple[dict[str, Any], str]:
    if not markdown_text.startswith("---\n"):
        return {}, markdown_text

    try:
        end_index = markdown_text.index("\n---\n", 4)
    except ValueError:
        return {}, markdown_text

    header_text = markdown_text[4:end_index]
    rest = markdown_text[end_index + 5 :]
    metadata = yaml.safe_load(header_text) or {}
    body = rest.lstrip("\n")
    return metadata, body


def render_front_matter(metadata: dict[str, Any], body: str) -> str:
    front_matter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{front_matter}\n---\n\n{body.rstrip()}\n"


def read_markdown_document(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    return extract_front_matter(text)


def write_markdown_document(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.write_text(render_front_matter(metadata, body), encoding="utf-8")


def markdown_to_html(markdown_text: str) -> str:
    try:
        import markdown as markdown_lib
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "`markdown` package is required for publish/update operations."
        ) from error

    body = re.sub(
        r'{{<\s*linkcard\s+url="([^"]+)"\s+title="([^"]*)"\s*>}}',
        lambda match: (
            f'<p><a href="{match.group(1)}">{match.group(2) or match.group(1)}</a></p>'
        ),
        markdown_text,
    )
    return markdown_lib.markdown(
        body,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
        output_format="html5",
    )


def prompt_input(label: str, default: str = "") -> str:
    prompt = f"{label}"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    value = input(prompt).strip()
    return value or default


class ZhihuClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self._profile: dict[str, Any] | None = None

    @classmethod
    def from_cookie_header(cls, cookie_header: str) -> "ZhihuClient":
        client = cls()
        client.session.cookies.update(parse_cookie_header(cookie_header))
        return client

    @classmethod
    def from_env_or_cache(
        cls,
        allow_login: bool,
        force_login: bool = False,
        cache_path: Path = COOKIE_FILE,
    ) -> "ZhihuClient":
        env_cookie = os.environ.get("ZHIHU_COOKIE", "").strip()
        client = cls.from_cookie_header(env_cookie) if env_cookie else cls()

        if not force_login and env_cookie and client.is_session_valid():
            return client

        if not force_login and not env_cookie:
            cached_cookie = load_cookie_cache(cache_path)
            if cached_cookie:
                cached_client = cls.from_cookie_header(cached_cookie)
                if cached_client.is_session_valid():
                    return cached_client

        if not allow_login:
            raise RuntimeError(
                "No valid Zhihu cookie found. Set ZHIHU_COOKIE for non-interactive runs."
            )

        client = cls.login_via_qrcode()
        save_cookie_cache(client.session, cache_path)
        return client

    def build_login_headers(self, is_polling: bool = False) -> dict[str, str]:
        headers = dict(LOGIN_HEADERS)
        xsrf_token = self.session.cookies.get("_xsrf")
        if xsrf_token:
            headers["x-xsrftoken"] = xsrf_token
        if is_polling:
            headers["Accept"] = "*/*"
            headers["Referer"] = "https://www.zhihu.com/signin?next=%2F"
            headers["sec-fetch-dest"] = "empty"
            headers["sec-fetch-mode"] = "cors"
            headers["sec-fetch-site"] = "same-origin"
            headers["x-zse-93"] = "101_3_3.0"
        return headers

    def prefetch_login_context(self) -> None:
        self.session.get(
            "https://www.zhihu.com/signin?next=%2F",
            headers={"User-Agent": USER_AGENT, "Referer": "https://www.zhihu.com/"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        self.session.post(
            UDID_API,
            headers=self.build_login_headers(),
            json={},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        self.session.get(
            CAPTCHA_V2_API,
            headers=self.build_login_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    @classmethod
    def login_via_qrcode(cls, timeout_seconds: int = 120) -> "ZhihuClient":
        client = cls()
        client.prefetch_login_context()

        response = client.session.post(
            QRCODE_API,
            headers=client.build_login_headers(),
            json={},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token") or payload.get("qrcode_token")
        link = payload.get("link")
        if not token or not link:
            raise RuntimeError(f"Failed to request Zhihu QR login: {payload}")

        client.print_qr_code(link)
        print(link)

        deadline = time.time() + timeout_seconds
        prompted_confirm = False
        prompted_risk_control = False
        while time.time() < deadline:
            response = client.session.get(
                f"{QRCODE_API}/{token}/scan_info",
                headers=client.build_login_headers(is_polling=True),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            try:
                scan_info = response.json()
            except Exception:
                scan_info = {}

            client.sync_scan_cookies(scan_info)

            if response.status_code == 403 and isinstance(scan_info.get("error"), dict):
                error = scan_info["error"]
                redirect = error.get("redirect")
                if error.get("code") == 40352 or error.get("need_login") is True:
                    if not prompted_risk_control:
                        prompted_risk_control = True
                        print("Zhihu requested a risk-control verification page.")
                        if redirect:
                            print(redirect)
                            open_url(redirect)
                    time.sleep(1.5)
                    continue

            if scan_info.get("status") == 1 and not prompted_confirm:
                prompted_confirm = True
                print("QR scanned. Confirm the login in the Zhihu app.")

            if client.is_login_successful(scan_info):
                try:
                    client.get_profile(refresh=True)
                except Exception:
                    pass
                if client.session.cookies.get("z_c0"):
                    return client

            time.sleep(1.0)

        raise TimeoutError("QR login timed out.")

    def print_qr_code(self, link: str) -> None:
        try:
            import qrcode
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "`qrcode` package is required for interactive login."
            ) from error

        print("Scan the QR code with the Zhihu app:")
        qr = qrcode.QRCode(border=1)
        qr.add_data(link)
        qr.make(fit=True)
        try:
            qr.print_ascii(invert=True)
        except Exception:
            pass

    def sync_scan_cookies(self, scan_info: dict[str, Any]) -> None:
        raw_cookie = []
        for key in ("cookie", "cookies"):
            value = scan_info.get(key)
            if isinstance(value, str):
                raw_cookie.append(value)

        skip_names = {
            "Domain",
            "Path",
            "Expires",
            "Max-Age",
            "HttpOnly",
            "Secure",
            "SameSite",
        }
        for item in ";".join(raw_cookie).split(";"):
            item = item.strip()
            if not item or "=" not in item:
                continue
            name, value = item.split("=", 1)
            if name in skip_names or not value:
                continue
            self.session.cookies.set(name, value, domain=".zhihu.com", path="/")

        if scan_info.get("z_c0"):
            self.session.cookies.set(
                "z_c0", scan_info["z_c0"], domain=".zhihu.com", path="/"
            )

    def is_login_successful(self, scan_info: dict[str, Any]) -> bool:
        if self.session.cookies.get("z_c0"):
            return True
        if scan_info.get("user_id") is not None:
            return True
        if (
            scan_info.get("access_token")
            or scan_info.get("success") is True
            or scan_info.get("logged_in") is True
        ):
            return True
        login_status = str(scan_info.get("login_status", "")).upper()
        return login_status in {
            "CONFIRMED",
            "LOGIN_SUCCESS",
            "SUCCESS",
            "OK",
            "LOGGED_IN",
        }

    def ensure_not_blocked(self, response: requests.Response) -> None:
        content = response.text
        blocked_text = [
            "系统监测到您的网络环境存在异常",
            "请求参数异常，请升级客户端后重试",
            "请点击下方验证按钮进行验证",
        ]
        if "account/unhuman" in response.url or any(
            text in content for text in blocked_text
        ):
            raise RuntimeError(
                "Zhihu blocked the current session. Refresh the cookie cache and complete the risk-control verification."
            )
        if "www.zhihu.com/signin" in response.url:
            raise RuntimeError("Zhihu cookie expired.")

    def is_session_valid(self) -> bool:
        try:
            self.get_profile(refresh=True)
            return True
        except Exception:
            return False

    def api_get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            url,
            headers=API_HEADERS,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def get_profile(self, refresh: bool = False) -> dict[str, Any]:
        if self._profile is not None and not refresh:
            return self._profile
        response = self.session.get(
            SELF_PROFILE_API,
            headers=API_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        self._profile = response.json()
        return self._profile

    @property
    def profile_name(self) -> str:
        return self.get_profile().get("name", "")

    @property
    def url_token(self) -> str:
        return self.get_profile()["url_token"]

    def paginate(
        self, url: str, key: str = "data", limit: int = 20
    ) -> list[dict[str, Any]]:
        offset = 0
        items: list[dict[str, Any]] = []
        while True:
            payload = self.api_get(url, {"offset": offset, "limit": limit})
            items.extend(payload.get(key, []))
            paging = payload.get("paging", {})
            if paging.get("is_end", True):
                break
            offset += limit
        return items

    def list_columns(self) -> list[ZhihuColumn]:
        url = (
            f"https://www.zhihu.com/api/v4/members/{self.url_token}/column-contributions"
            "?include=data%5B*%5D.column.intro%2Cfollowers%2Carticles_count"
        )
        data = self.paginate(url)
        return [ZhihuColumn.from_api(item) for item in data]

    def list_articles(self) -> list[ZhihuArticle]:
        url = (
            f"https://www.zhihu.com/api/v4/members/{self.url_token}/articles"
            "?include=data%5B*%5D.column%2Cauthor%2Ccomment_count%2Cvoteup_count"
        )
        data = self.paginate(url)
        return [ZhihuArticle.from_api(item) for item in data]

    def fetch_article_html(self, url: str) -> str:
        response = self.session.get(
            url, headers=PAGE_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        self.ensure_not_blocked(response)
        return response.text

    def download(self, url: str) -> bytes | None:
        for _ in range(3):
            try:
                response = self.session.get(
                    url, headers=PAGE_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS
                )
                response.raise_for_status()
                return response.content
            except Exception as error:
                print(f"Download failed for {url}: {error}", flush=True)
                time.sleep(1)
        return None

    def sync_articles(self, output_dir: Path, delay_seconds: float = 0) -> None:
        articles = self.list_articles()
        total_articles = len(articles)
        Parser.urls_map = {
            article.url: f"https://www.ykiko.me/zh-cn/articles/{article.id}"
            for article in articles
        }
        parser = Parser()

        started_at = time.monotonic()
        for index, article in enumerate(articles, start=1):
            article_started_at = time.monotonic()
            print(f"[{index}/{total_articles}] Fetching {article.id}...", flush=True)
            html = self.fetch_article_html(article.url)
            parsed_article = parser.parse_article_from_html(html)
            markdown_text = self.render_synced_markdown(
                article.id,
                parsed_article.title,
                parsed_article.created,
                parsed_article.updated,
                parsed_article.content.dump(),
                article.url,
                article.column_id,
                article.column_title,
                output_dir / article.id / "index.md",
            )
            self.write_article_files(
                output_dir,
                article.id,
                markdown_text,
                parsed_article.cover,
            )
            elapsed = time.monotonic() - article_started_at
            print(
                f"[{index}/{total_articles}] Done: {article.id} ({elapsed:.2f}s)",
                flush=True,
            )
            if delay_seconds > 0:
                time.sleep(delay_seconds)

        total_elapsed = time.monotonic() - started_at
        print(f"All done in {total_elapsed:.2f}s", flush=True)

    def render_synced_markdown(
        self,
        article_id: str,
        title: str,
        created: int,
        updated: int,
        body: str,
        article_url: str,
        column_id: str | None,
        column_title: str | None,
        existing_path: Path,
    ) -> str:
        existing_metadata: dict[str, Any] = {}
        if existing_path.exists():
            existing_metadata, _ = read_markdown_document(existing_path)

        reserved_keys = {
            "title",
            "date",
            "updated",
            "zhihu_article_id",
            "zhihu_url",
            "zhihu_column_id",
            "zhihu_column_title",
        }
        metadata = {
            key: value
            for key, value in existing_metadata.items()
            if key not in reserved_keys
        }
        metadata.update(
            {
                "title": title,
                "date": datetime.fromtimestamp(created, tz=_TZ_SHANGHAI).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "updated": datetime.fromtimestamp(updated, tz=_TZ_SHANGHAI).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "zhihu_article_id": article_id,
                "zhihu_url": article_url,
            }
        )
        if column_id:
            metadata["zhihu_column_id"] = column_id
        if column_title:
            metadata["zhihu_column_title"] = column_title
        return render_front_matter(metadata, body)

    def write_article_files(
        self, base_dir: Path, article_id: str, markdown_text: str, cover_url: str
    ) -> None:
        article_dir = base_dir / article_id
        article_dir.mkdir(parents=True, exist_ok=True)
        (article_dir / "index.md").write_text(markdown_text, encoding="utf-8")
        if cover_url:
            content = self.download(cover_url)
            if content is not None:
                with open(article_dir / "featured.png", "wb") as file:
                    file.write(content)

    def create_or_update_article(
        self,
        markdown_path: Path,
        article_id: str | None,
        column: ZhihuColumn | None,
    ) -> str:
        metadata, body_markdown = read_markdown_document(markdown_path)
        title = metadata.get("title") or markdown_path.stem
        html = markdown_to_html(body_markdown)
        title_image = metadata.get("zhihu_title_image_url") or metadata.get(
            "title_image_url"
        )

        if article_id:
            target_id = str(article_id)
        else:
            create_response = self.session.post(
                f"{ZHUANLAN_API}/drafts",
                json={"title": title, "delta_time": 0},
                headers=ZHUANLAN_HEADERS,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            create_response.raise_for_status()
            target_id = str(create_response.json()["id"])

        patch_response = self.session.patch(
            f"{ZHUANLAN_API}/{target_id}/draft",
            json={
                "content": html,
                "title": title,
                "titleImage": title_image,
                "isTitleImageFullScreen": False,
            },
            headers=ZHUANLAN_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        patch_response.raise_for_status()

        publish_response = self.session.put(
            f"{ZHUANLAN_API}/{target_id}/publish",
            json={
                "column": (
                    {
                        "id": column.id,
                        "title": column.title,
                    }
                    if column
                    else None
                ),
                "commentPermission": "anyone",
            },
            headers=ZHUANLAN_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        publish_response.raise_for_status()

        metadata["zhihu_article_id"] = target_id
        metadata["zhihu_url"] = f"https://zhuanlan.zhihu.com/p/{target_id}"
        if column:
            metadata["zhihu_column_id"] = column.id
            metadata["zhihu_column_title"] = column.title
        write_markdown_document(markdown_path, metadata, body_markdown)
        return target_id

    def request_new_column(self) -> None:
        print(f"Open this page to request a new column: {COLUMN_REQUEST_URL}")
        if not open_url(COLUMN_REQUEST_URL):
            print(
                "Automatic browser launch is unavailable in this terminal. Open the URL manually."
            )
