import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from zhihu_client import (
    COOKIE_FILE,
    ZhihuClient,
    format_cookie_header,
    save_cookie_cache,
    save_github_secret,
)
from zhihu_tui import MenuAction, run_menu as run_action_menu, run_text_input

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLE_OUTPUT_DIR = BASE_DIR / "website" / "content" / "zh-cn" / "articles"
console = Console()


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def build_client(
    force_login: bool = False, allow_login: bool | None = None
) -> ZhihuClient:
    if allow_login is None:
        allow_login = is_interactive()
    return ZhihuClient.from_env_or_cache(
        allow_login=allow_login,
        force_login=force_login,
    )


def sync_articles(client: ZhihuClient) -> None:
    delay_seconds = float(os.environ.get("ZHIHU_DELAY_SECONDS", "0"))
    client.sync_articles(ARTICLE_OUTPUT_DIR, delay_seconds=delay_seconds)
    run_markdown_format()


def run_markdown_format() -> None:
    if not (BASE_DIR / "pixi.toml").exists():
        console.print("[yellow]Skip formatting: pixi.toml not found.[/]")
        return
    if shutil.which("pixi") is None:
        raise RuntimeError(
            "pixi is required to format synced markdown. Install pixi and rerun the sync."
        )
    console.print("[cyan]Formatting repository via pixi...[/]")
    subprocess.run(
        ["pixi", "run", "-e", "format", "format"],
        cwd=BASE_DIR,
        check=True,
    )


def format_timestamp(timestamp: int) -> str:
    if timestamp <= 0:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def browse_columns(client: ZhihuClient) -> None:
    columns = client.list_columns()
    if not columns:
        console.print("[yellow]No columns found.[/]")
        return
    actions = [
        MenuAction(
            key=column.id,
            label=column.title,
            description=(
                f"id={column.id}\n"
                f"followers={column.followers}\n"
                f"articles={column.articles_count}"
                + (f"\n\n{column.intro}" if column.intro else "")
            ),
        )
        for column in columns
    ]
    run_action_menu(
        "Zhihu Columns",
        "Browse your columns. q or Enter to go back.",
        actions,
        browse_only=True,
    )


def print_columns(client: ZhihuClient) -> None:
    columns = client.list_columns()
    if not columns:
        print("No columns found.")
        return
    for column in columns:
        print(f"{column.title} ({column.id})")
        print(f"  followers={column.followers} articles={column.articles_count}")
        if column.intro:
            print(f"  intro={column.intro}")


def browse_articles(client: ZhihuClient) -> None:
    articles = client.list_articles()
    if not articles:
        console.print("[yellow]No articles found.[/]")
        return
    actions = [
        MenuAction(
            key=article.id,
            label=article.title,
            description=(
                f"id={article.id}\n"
                f"column={article.column_title or '-'}\n"
                f"created={format_timestamp(article.created)}\n"
                f"updated={format_timestamp(article.updated)}\n"
                f"url={article.url}"
            ),
        )
        for article in articles
    ]
    run_action_menu(
        "Zhihu Articles",
        "Browse your articles. q or Enter to go back.",
        actions,
        browse_only=True,
    )


def print_articles(client: ZhihuClient) -> None:
    articles = client.list_articles()
    if not articles:
        print("No articles found.")
        return
    for article in articles:
        column_text = article.column_title or "-"
        print(f"{article.id} | {article.title} | column={column_text}")


def export_cookie(
    client: ZhihuClient,
    save_path: str = "",
    gh_secret: str = "",
    show_value: bool | None = None,
) -> None:
    cookie_header = format_cookie_header(client.session)
    if show_value is None:
        show_value = is_interactive()
    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cookie_header + "\n", encoding="utf-8")
        print(f"Saved cookie to {path}")
    if gh_secret:
        save_github_secret(gh_secret, cookie_header)
        print(f"Updated GitHub secret {gh_secret}")
    if show_value:
        if not is_interactive():
            print(f"::add-mask::{cookie_header}")
        print(f"ZHIHU_COOKIE={cookie_header}")
    elif not save_path and not gh_secret:
        raise RuntimeError(
            "Refusing to print cookie in non-interactive mode. Use --stdout, --save, or --gh-secret."
        )


def select_column(client: ZhihuClient, allow_none: bool = True):
    columns = client.list_columns()
    actions: list[MenuAction] = []
    if allow_none:
        actions.append(
            MenuAction(
                key="__none__",
                label="No column",
                description="Publish without attaching the article to a Zhihu column.",
            )
        )
    actions.extend(
        MenuAction(
            key=column.id,
            label=column.title,
            description=f"followers={column.followers} | articles={column.articles_count}"
            + (f"\n\n{column.intro}" if column.intro else ""),
        )
        for column in columns
    )
    selected_key = run_action_menu(
        "Select Column", "Choose the target Zhihu column", actions
    )
    if selected_key is None:
        return None
    if selected_key == "__none__":
        return None
    for column in columns:
        if column.id == selected_key:
            return column
    return None


def select_article(client: ZhihuClient):
    articles = client.list_articles()
    actions = [
        MenuAction(
            key=article.id,
            label=article.title,
            description=f"id={article.id}\ncolumn={article.column_title or '-'}",
        )
        for article in articles
    ]
    selected_key = run_action_menu(
        "Select Article", "Choose the Zhihu article to update", actions
    )
    if selected_key is None:
        return None
    for article in articles:
        if article.id == selected_key:
            return article
    return None


def prompt_markdown_path(initial_value: str = "") -> Path | None:
    raw_path = run_text_input(
        "Markdown Path",
        "Enter the local markdown file path",
        "Path to the markdown file",
        value=initial_value,
        placeholder="content/posts/example.md",
    )
    if raw_path is None:
        return None
    markdown_path = Path(raw_path).expanduser().resolve()
    if not markdown_path.exists():
        raise FileNotFoundError(markdown_path)
    return markdown_path


def publish_new_article(client: ZhihuClient) -> None:
    markdown_path = prompt_markdown_path()
    if markdown_path is None:
        return
    column = select_column(client, allow_none=True)
    article_id = client.create_or_update_article(
        markdown_path, article_id=None, column=column
    )
    console.print(f"[green]Published:[/] https://zhuanlan.zhihu.com/p/{article_id}")


def update_existing_article(client: ZhihuClient) -> None:
    article = select_article(client)
    if article is None:
        return
    default_local_path = ARTICLE_OUTPUT_DIR / article.id / "index.md"
    markdown_path = prompt_markdown_path(
        initial_value=str(default_local_path) if default_local_path.exists() else ""
    )
    if markdown_path is None:
        return
    default_column = None
    if article.column_id:
        for column in client.list_columns():
            if column.id == article.column_id:
                default_column = column
                break
    console.print(f"[cyan]Current article:[/] {article.title} ({article.id})")
    if default_column:
        selected = run_action_menu(
            "Update Article",
            f"Current column: {default_column.title}",
            [
                MenuAction(
                    key="current",
                    label=f"Use {default_column.title}",
                    description="Keep the article in its current Zhihu column.",
                ),
                MenuAction(
                    key="choose",
                    label="Choose another column",
                    description="Open the column selector and pick a different target column.",
                ),
                MenuAction(
                    key="none",
                    label="Remove column",
                    description="Publish the article without attaching it to a Zhihu column.",
                ),
            ],
        )
        if selected is None:
            return
        if selected == "current":
            column = default_column
        elif selected == "choose":
            column = select_column(client, allow_none=True)
        else:
            column = None
    else:
        column = select_column(client, allow_none=True)
    updated_id = client.create_or_update_article(
        markdown_path, article_id=article.id, column=column
    )
    console.print(f"[green]Updated:[/] https://zhuanlan.zhihu.com/p/{updated_id}")


def login_and_cache() -> ZhihuClient:
    client = build_client(force_login=True, allow_login=True)
    save_cookie_cache(client.session, COOKIE_FILE)
    console.print(
        Panel(
            f"[bold green]Logged in as[/] {client.profile_name}\n"
            f"[bold]Cookie cache[/] {COOKIE_FILE}",
            title="Zhihu Login",
            border_style="green",
        )
    )
    return client


def build_menu_actions() -> list[tuple[MenuAction, object]]:
    return [
        (
            MenuAction(
                key="sync",
                label="Sync all articles",
                description="Fetch all of your Zhihu articles and update website/content/zh-cn/articles.",
            ),
            lambda client: sync_articles(client),
        ),
        (
            MenuAction(
                key="columns",
                label="Browse columns",
                description="Open a TUI browser for all of your Zhihu columns, including follower counts and article counts.",
            ),
            lambda client: browse_columns(client),
        ),
        (
            MenuAction(
                key="articles",
                label="Browse articles",
                description="Open a TUI browser for all of your Zhihu articles and their attached columns.",
            ),
            lambda client: browse_articles(client),
        ),
        (
            MenuAction(
                key="publish",
                label="Publish markdown",
                description="Select a local markdown file, choose a column, and publish it as a new Zhihu article.",
            ),
            lambda client: publish_new_article(client),
        ),
        (
            MenuAction(
                key="update",
                label="Update existing article",
                description="Pick one of your published Zhihu articles and update it from a local markdown file.",
            ),
            lambda client: update_existing_article(client),
        ),
        (
            MenuAction(
                key="request_column",
                label="Request new column",
                description="Open the official Zhihu column application page in your browser.",
            ),
            lambda client: client.request_new_column(),
        ),
        (
            MenuAction(
                key="login",
                label="Refresh login",
                description="Force QR-code login again and refresh the cached cookie in .cookie/zhihu.yaml.",
            ),
            lambda _client: login_and_cache(),
        ),
        (
            MenuAction(
                key="export_cookie",
                label="Export cookie",
                description="Print the current ZHIHU_COOKIE and save it to a local text file for GitHub Actions.",
            ),
            lambda client: export_cookie(
                client, save_path=str(COOKIE_FILE.with_suffix(".txt"))
            ),
        ),
    ]


def run_menu() -> None:
    client = build_client(allow_login=True)
    while True:
        menu_items = build_menu_actions()
        selected_key = run_action_menu(
            "Zhihu Toolkit",
            f"user={client.profile_name} | cache={COOKIE_FILE}",
            [item[0] for item in menu_items],
        )
        if selected_key is None:
            return
        action = next(
            (callback for action, callback in menu_items if action.key == selected_key),
            None,
        )
        if action is None:
            return
        print()
        try:
            result = action(client)
            if isinstance(result, ZhihuClient):
                client = result
        except KeyboardInterrupt:
            console.print("[yellow]Action cancelled.[/]")
        except Exception as error:
            console.print(Panel(str(error), title="Action Failed", border_style="red"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zhihu_cli.py",
        description="Zhihu toolkit for local QR login, syncing, browsing, and publishing articles.",
        epilog=(
            "Examples:\n"
            "  uv run python scripts/zhihu_cli.py\n"
            "  uv run python scripts/zhihu_cli.py sync\n"
            "  uv run python scripts/zhihu_cli.py login --gh-secret ZHIHU_COOKIE\n"
            "  uv run python scripts/zhihu_cli.py publish path/to/article.md\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("menu", help="Open the local interactive menu.")
    subparsers.add_parser(
        "sync", help="Sync all Zhihu articles into the website content directory."
    )
    subparsers.add_parser("columns", help="List all of your Zhihu columns.")
    subparsers.add_parser("articles", help="List all of your Zhihu articles.")
    subparsers.add_parser(
        "request-column", help="Open the official Zhihu new-column request page."
    )

    login_parser = subparsers.add_parser(
        "login", help="Force QR login and refresh the local cookie cache."
    )
    login_parser.add_argument("--save", default="")
    login_parser.add_argument("--gh-secret", default="")
    login_parser.add_argument("--stdout", action="store_true")

    export_parser = subparsers.add_parser(
        "export-cookie", help="Export the current cookie to stdout/file/GitHub secret."
    )
    export_parser.add_argument("--save", default="")
    export_parser.add_argument("--gh-secret", default="")
    export_parser.add_argument("--stdout", action="store_true")

    publish_parser = subparsers.add_parser(
        "publish", help="Publish a local markdown file as a new Zhihu article."
    )
    publish_parser.add_argument("markdown_path")

    update_parser = subparsers.add_parser(
        "update-article", help="Update an existing Zhihu article from a markdown file."
    )
    update_parser.add_argument(
        "markdown_path",
        nargs="?",
        default="",
        help="Path to the markdown file. Defaults to website/content/zh-cn/articles/<article-id>/index.md.",
    )
    update_parser.add_argument("--article-id", default="")

    preview_parser = subparsers.add_parser(
        "preview", help="Push draft content and print the Zhihu preview URL."
    )
    preview_parser.add_argument(
        "markdown_path",
        nargs="?",
        default="",
        help="Path to the markdown file. Defaults to website/content/zh-cn/articles/<article-id>/index.md.",
    )
    preview_parser.add_argument("--article-id", default="")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        if is_interactive():
            run_menu()
            return
        client = build_client(allow_login=False)
        sync_articles(client)
        return

    if args.command == "menu":
        run_menu()
        return

    if args.command == "login":
        client = login_and_cache()
        export_cookie(
            client,
            save_path=args.save,
            gh_secret=args.gh_secret,
            show_value=args.stdout or None,
        )
        return

    if args.command == "export-cookie":
        client = build_client(allow_login=True)
        export_cookie(
            client,
            save_path=args.save,
            gh_secret=args.gh_secret,
            show_value=args.stdout or None,
        )
        return

    client = build_client(allow_login=is_interactive())

    if args.command == "sync":
        sync_articles(client)
    elif args.command == "columns":
        print_columns(client)
    elif args.command == "articles":
        print_articles(client)
    elif args.command == "request-column":
        client.request_new_column()
    elif args.command == "publish":
        markdown_path = Path(args.markdown_path).expanduser().resolve()
        if not markdown_path.exists():
            raise FileNotFoundError(markdown_path)
        column = select_column(client, allow_none=True) if is_interactive() else None
        article_id = client.create_or_update_article(
            markdown_path, article_id=None, column=column
        )
        print(f"Published new article: https://zhuanlan.zhihu.com/p/{article_id}")
    elif args.command == "update-article":
        article_id = args.article_id.strip() if args.article_id else ""
        raw_path = args.markdown_path.strip() if args.markdown_path else ""
        if not raw_path:
            if not article_id:
                parser.error(
                    "Either provide markdown_path or --article-id to derive the local file path."
                )
            raw_path = str(ARTICLE_OUTPUT_DIR / article_id / "index.md")
        markdown_path = Path(raw_path).expanduser().resolve()
        if not markdown_path.exists():
            raise FileNotFoundError(markdown_path)
        if not article_id:
            from zhihu_client import read_markdown_document

            metadata, _ = read_markdown_document(markdown_path)
            article_id = str(metadata.get("zhihu_article_id", "")).strip()
        if not article_id:
            raise RuntimeError(
                "No article id provided. Use --article-id or add zhihu_article_id to front matter."
            )
        column = select_column(client, allow_none=True) if is_interactive() else None
        updated_id = client.create_or_update_article(
            markdown_path, article_id=article_id, column=column
        )
        print(f"Updated article: https://zhuanlan.zhihu.com/p/{updated_id}")
    elif args.command == "preview":
        article_id = args.article_id.strip() if args.article_id else ""
        raw_path = args.markdown_path.strip() if args.markdown_path else ""
        if not raw_path:
            if not article_id:
                parser.error(
                    "Either provide markdown_path or --article-id to derive the local file path."
                )
            raw_path = str(ARTICLE_OUTPUT_DIR / article_id / "index.md")
        markdown_path = Path(raw_path).expanduser().resolve()
        if not markdown_path.exists():
            raise FileNotFoundError(markdown_path)
        if not article_id:
            from zhihu_client import read_markdown_document

            metadata, _ = read_markdown_document(markdown_path)
            article_id = str(metadata.get("zhihu_article_id", "")).strip()
        if not article_id:
            raise RuntimeError(
                "No article id provided. Use --article-id or add zhihu_article_id to front matter."
            )
        preview_url = client.preview_article(markdown_path, article_id)
        print(f"Preview URL: {preview_url}")
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
