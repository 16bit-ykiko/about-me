import os
import json
import requests
import markdown2 as markdown

from urllib.parse import unquote
from bs4 import BeautifulSoup, Tag, PageElement


class Article:
    def __init__(self, content: markdown.Document, title: str, cover: str, created: int, updated: int):
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
    languages_map = {
        "nasm": "x86asm",
        "text": "bash"
    }

    def parse_article(self, text: str) -> Article:
        soup = BeautifulSoup(text, 'html.parser')

        # 这里存放的是正文
        body = soup.select('div[class^="RichText"]')[0]
        content = self.parse_body(body)

        # 这里存的是文章的一些信息
        jsinitdata = json.loads(soup.select(
            'script[id="js-initialData"]')[0].get_text())

        articles = jsinitdata["initialState"]["entities"]["articles"]
        inner = articles[list(articles.keys())[0]]

        title = inner["title"]  # 标题
        cover = inner["imageUrl"]  # 封面
        created = inner["created"]  # 创建时间
        updated = inner["updated"]  # 更新时间

        return Article(content, title, cover, created, updated)

    def parse_answer(self, text: str) -> Answer:
        pass

    def parse_body(self, element: Tag) -> markdown.Document:
        nodes = []
        for child in element.children:
            match child.name:
                case 'h2':
                    nodes.append(markdown.Header(1, child.text))
                case 'h3':
                    nodes.append(markdown.Header(2, child.text))
                case 'hr':
                    nodes.append(markdown.HorizontalRule())
                case 'p':
                    nodes.append(self.parse_paragraph(child))
                case 'a':
                    nodes.append(self.parse_linkcard(child))
                case 'ul' | 'ol':
                    nodes.append(self.parse_list(child))
                case 'div':
                    nodes.append(self.parse_div(child))
                case 'blockquote':
                    nodes.append(self.parse_blockquote(child))
                case 'figure':
                    nodes.append(self.parse_image(child))
                case _:
                    raise ValueError(f"Unknown element: {child}")

        return markdown.Document(nodes)

    def parse_paragraph(self, element: Tag) -> markdown.Paragraph:
        nodes = []
        for child in element.children:
            match child.name:
                case 'a':
                    nodes.append(self.parse_link(child))
                case 'b':
                    nodes.append(markdown.Strong(child.text))
                case 'i':
                    nodes.append(markdown.Emphasis(child.text))
                case'code':
                    nodes.append(markdown.InlineCode(child.text))
                case 'br':
                    nodes.append(markdown.NewLine())
                case 'hr':
                    nodes.append(markdown.HorizontalRule())
                case None:
                    nodes.append(markdown.Text(child))
                case _:
                    raise ValueError(f"Unknown element: {child}")

        return markdown.Paragraph(nodes)

    def normalize_url(self, url: str) -> str:
        url = unquote(url.replace('//link.zhihu.com/?target=https%3A', ""))
        return self.urls_map.get(url, url)

    def parse_link(self, element: Tag) -> markdown.Link:
        url = self.normalize_url(element['href'])
        return markdown.Link(element.text, url)

    def parse_linkcard(self, element: Tag) -> markdown.LinkCard:
        title = element.attrs.get("data-text")
        url = self.normalize_url(element['href'])
        return markdown.LinkCard(title if title else "", url)

    def parse_image(self, element: Tag) -> markdown.Image:
        noscript = element.find('noscript')
        img = noscript.find('img')
        attributes = ["data-original", "data-default-watermark-src", "src"]
        src = None

        for attr in attributes:
            src = img.attrs.get(attr)
            if src is not None:
                break

        if src is None:
            raise ValueError("Image src not found")

        src = self.normalize_url(src)
        figcaption = element.find('figcaption')
        return markdown.Image(figcaption.text if figcaption else "", src)

    def parse_list(self, element: Tag) -> markdown.List:
        nodes = []
        for child in element.children:
            match child.name:
                case 'li':
                    nodes.append(self.parse_paragraph(child))
                case "ul" | "ol":
                    nodes.append(self.parse_list(child))
                case _:
                    raise ValueError(f"Unknown element: {child}")

        if element.name == 'ul':
            return markdown.List(False, nodes)
        else:
            return markdown.List(True, nodes)

    def parse_div(self, element: Tag) -> markdown.BlockCode:
        pre = element.find('pre')
        code = pre.find('code')
        text = code.text.removesuffix('\n')
        language = code['class'][0].removeprefix('language-')
        language = self.languages_map.get(language, language)
        return markdown.BlockCode(text, language)

    def parse_blockquote(self, element: PageElement) -> markdown.BlockQuote:
        return markdown.BlockQuote(self.parse_paragraph(element))
