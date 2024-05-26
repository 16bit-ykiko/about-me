
from requests import get
from urllib.parse import unquote
from bs4 import BeautifulSoup, PageElement, Tag

urls_map = {}
language_map = {
    "nasm": "x86asm",
    "text": "bash"
}


def toMarkdown(page: Tag):
    result = []
    for element in page.children:
        match element.name:
            case 'p':
                result.append("\n\n" + paragraph(element))
            case 'a':
                result.append("\n\n" + link_card(element))
            case 'h2':
                result.append(f'\n\n## {paragraph(element)}')
            case 'h3':
                result.append(f'\n\n### {paragraph(element)}')
            case 'ul':
                result.append("\n\n" + unordered_list(element))
            case 'div':
                result.append("\n\n" + code_block(element))
            case 'blockquote':
                result.append("\n\n" + f"> {element.text}")
    return "".join(result)


# 处理文本段落
def paragraph(element: PageElement) -> str:
    result = ""
    for element in element.children:
        match element.name:
            case 'a':
                result += link(element)
            case 'b':
                result += f'**{element.text}**'
            case 'code':
                result += f'`{element.text}`'
            case None:
                result += element.text
    return result


# 把链接归一化
def normalize(url: str) -> str:
    # 去掉知乎加的链接图
    url = unquote(url.replace('//link.zhihu.com/?target=https%3A', ""))
    # 如果有映射，就替换
    if url in urls_map:
        url = urls_map[url]
    return url


# 处理图片
def image(element: PageElement) -> str:
    noscript = element.find('noscript')
    img = noscript.find('img')
    # 可能出现链接的属性
    attributes = ["data-original", "data-default-watermark-src", "src"]
    src = None
    for attr in attributes:
        src = img.attrs.get(attr)
        if src is not None:
            break
    return f'![]({src})'


# 处理链接
def link(element: PageElement) -> str:
    url = normalize(element['href'])
    return f'[{element.text}]({url})'


# 处理无序列表
def unordered_list(element: PageElement, tab=0) -> str:
    result = ""
    for element in element.children:
        match element.name:
            case 'li':
                for _ in range(tab):
                    result += '\t'
                result += f'- {paragraph(element)}\n'
            case "ul":
                result += unordered_list(element, tab + 1)
    return result


# 处理代码块
def code_block(element: PageElement) -> str:
    pre = element.find('pre')
    code = pre.find('code')
    lang: str = code['class'][0]
    lang = lang.replace('language-', '')
    lang = language_map.get(lang, lang)
    text: str = code.get_text()
    return "```" + lang + "\n" + text + ("" if text.endswith("\n") else "\n") + "```"


# 处理卡片链接 ---- hexo 插件扩展语法
def link_card(element: PageElement) -> str:
    url = normalize(element['href'])
    title = element.attrs.get("data-text")
    if title == None:
        soup = BeautifulSoup(get(url).text, 'html.parser')
        title = soup.title.string
        if title.endswith("| BLOGS"):
            title = title[:-7]

    return "---\n\n" + title + "\n" + url + "\n\n---"
