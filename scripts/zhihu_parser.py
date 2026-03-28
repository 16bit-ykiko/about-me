import json
import re
import markdown_ast as markdown

from urllib.parse import unquote
from bs4 import BeautifulSoup, Tag, PageElement


class Article:
    def __init__(
        self,
        content: markdown.Document,
        title: str,
        cover: str,
        created: int,
        updated: int,
    ):
        self.content = content
        self.title = title
        self.cover = cover
        self.created = created
        self.updated = updated


class Answer:
    def __init__(self, author: str, content: markdown.Document):
        self.author = author
        self.content = content


class Parser:
    urls_map = {}
    languages_map = {"nasm": "x86asm", "text": "bash"}

    @staticmethod
    def warn_skip(tag_name: str, context: str) -> None:
        print(f"Warning: skipping unsupported <{tag_name}> in {context}", flush=True)

    def parse_article_from_html(self, text: str) -> Article:
        soup = BeautifulSoup(text, "html.parser")
        initial_data = soup.select_one('script[id="js-initialData"]')
        if initial_data is not None:
            jsinitdata = json.loads(initial_data.get_text())
            articles = jsinitdata["initialState"]["entities"]["articles"]
            inner = articles[list(articles.keys())[0]]
            soup = BeautifulSoup(inner["content"], "html.parser")
            content = self.parse_body(soup)
            title = inner["title"]
            cover = (
                inner.get("imageUrl")
                or inner.get("image_url")
                or inner.get("titleImage")
                or inner.get("title_image", "")
            )
            created = inner["created"]
            updated = inner["updated"]
            return Article(content, title, cover, created, updated)

        body = soup.select_one('div.RichText, div[class*="RichText"]')
        if body is None:
            raise ValueError("Article body not found")

        content = self.parse_body(body)
        return Article(content, "", "", 0, 0)

    def parse_article_from_json(self, text: str) -> Article:
        inner = json.loads(text)

        soup = BeautifulSoup(inner["content"], "html.parser")
        content = self.parse_body(soup)  # 正文
        title = inner["title"]  # 标题
        cover = inner.get("image_url") or inner.get("title_image", "")  # 封面
        created = inner["created"]  # 创建时间
        updated = inner["updated"]  # 更新时间

        return Article(content, title, cover, created, updated)

    def parse_answer(self, text: str) -> Answer:
        pass

    def parse_body(self, element: Tag) -> markdown.Document:
        nodes = []
        for child in element.children:
            if child.name is None:
                if child.text.strip():
                    nodes.append(
                        markdown.Paragraph([markdown.Text(child.text.strip())])
                    )
                continue
            match child.name:
                case "h2":
                    nodes.append(markdown.Header(2, child.text))
                case "h3":
                    nodes.append(markdown.Header(3, child.text))
                case "hr":
                    nodes.append(markdown.HorizontalRule())
                case "p":
                    nodes.append(self.parse_paragraph(child))
                case "a":
                    nodes.append(self.parse_linkcard(child))
                case "ul" | "ol":
                    node = self.parse_list(child)
                    if node is not None:
                        nodes.append(node)
                case "div":
                    node = self.parse_div(child)
                    if node is not None:
                        nodes.append(node)
                case "blockquote":
                    nodes.append(self.parse_blockquote(child))
                case "figure":
                    node = self.parse_image(child)
                    if node is not None:
                        nodes.append(node)
                case _:
                    self.warn_skip(child.name, "article body")

        return markdown.Document(nodes)

    @staticmethod
    def _norm(text: str) -> str:
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\\([_*\[\]()~`>#+\-.!|{}])", r"\1", text)
        return text

    def parse_paragraph(self, element: Tag) -> markdown.Paragraph:
        nodes = []
        for child in element.children:
            if child.name is None:
                if child.text:
                    nodes.append(markdown.Text(self._norm(child.text)))
                continue
            match child.name:
                case "a":
                    nodes.append(self.parse_link(child))
                case "b" | "strong":
                    nodes.append(markdown.Strong(self._norm(child.text)))
                case "i" | "em":
                    nodes.append(markdown.Emphasis(self._norm(child.text)))
                case "code":
                    nodes.append(markdown.InlineCode(child.text))
                case "br":
                    nodes.append(markdown.NewLine())
                case "hr":
                    nodes.append(markdown.HorizontalRule())
                case None | "span":
                    # span 对应知乎新加的可以点击的标签，例如：
                    # <span data-search-entity="7">五月一号</span>
                    if child.text:
                        nodes.append(markdown.Text(self._norm(child.text)))
                case "sup" | "sub" | "section":
                    if child.text:
                        nodes.append(markdown.Text(self._norm(child.text)))
                case _:
                    self.warn_skip(child.name, "paragraph")

        return markdown.Paragraph(nodes)

    def normalize_url(self, url: str) -> str:
        url = unquote(url.replace("//link.zhihu.com/?target=https%3A", ""))
        return self.urls_map.get(url, url)

    def parse_link(self, element: Tag) -> markdown.Link:
        url = self.normalize_url(element["href"])
        return markdown.Link(element.text, url)

    def parse_linkcard(self, element: Tag) -> markdown.LinkCard:
        title = element.attrs.get("data-text")
        url = self.normalize_url(element["href"])
        return markdown.LinkCard(title if title else "", url)

    def parse_image(self, element: Tag) -> markdown.Image | None:
        img = element.find("img")
        if img is None:
            noscript = element.find("noscript")
            img = noscript.find("img") if noscript else None
        if img is None:
            self.warn_skip("figure", "image parsing")
            return None

        attributes = ["data-original", "data-default-watermark-src", "src"]
        src = None

        for attr in attributes:
            src = img.attrs.get(attr)
            if src is not None:
                break

        if src is None:
            raise ValueError("Image src not found")

        src = self.normalize_url(src)
        figcaption = element.find("figcaption")
        return markdown.Image(figcaption.text if figcaption else "", src)

    def parse_list(self, element: Tag) -> markdown.Node | None:
        nodes = []
        for child in element.children:
            if child.name is None:
                continue
            match child.name:
                case "li":
                    nodes.append(self.parse_paragraph(child))
                case "ul" | "ol":
                    node = self.parse_list(child)
                    if node is not None:
                        nodes.append(node)
                case _:
                    self.warn_skip(child.name, "list")

        if not nodes:
            return None
        return markdown.List(element.name == "ol", nodes)

    def parse_div(self, element: Tag) -> markdown.Node | None:
        pre = element.find("pre")
        if pre is None:
            self.warn_skip("div", "block parsing")
            return None
        code = pre.find("code")
        if code is None:
            self.warn_skip("pre", "code block parsing")
            return None
        text = code.text.removesuffix("\n")
        classes = code.get("class", [])
        language = classes[0].removeprefix("language-") if classes else ""
        language = self.languages_map.get(language, language)
        return markdown.BlockCode(text, language)

    def parse_blockquote(self, element: PageElement) -> markdown.BlockQuote:
        return markdown.BlockQuote(self.parse_paragraph(element))
