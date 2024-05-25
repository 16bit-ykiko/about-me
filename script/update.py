import os
import json
import datetime
import requests

from typing import Iterable
from urllib.parse import unquote
from bs4 import BeautifulSoup, PageElement

urls_map = {}
cookies = {}


def get(url: str):
    n = 0
    headers = {
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    while n < 5:
        try:
            return requests.get(url, timeout=10, cookies=cookies, headers=headers)
        except Exception as e:
            n += 1


def image(element: PageElement) -> str:
    noscript = element.find('noscript')
    img = noscript.find('img')
    src = img.attrs.get("data-original")
    if src == None:
        src = img.attrs.get("data-default-watermark-src")
    if src == None:
        src = img.attrs.get("src")
    return f'![img]({src})'


def normalize(url: str) -> str:
    url = unquote(url.replace('//link.zhihu.com/?target=https%3A', ""))
    if url in urls_map:
        url = urls_map[url]
    return url


def link(element: PageElement) -> str:
    url = normalize(element['href'])
    return f'[{element.text}]({url})'


def link_card(element: PageElement) -> str:
    url = normalize(element['href'])
    title = element.attrs.get("data-text")
    if title == None:
        soup = BeautifulSoup(get(url).text, 'html.parser')
        title = soup.title.string
        if title.endswith("| BLOGS"):
            title = title[:-7]

    return "---\n\n" + title + "\n" + url + "\n\n---"


def paragraph(element: PageElement) -> str:
    result = ""
    for element in element.children:
        match element.name:
            case 'a':
                result += link(element)
            case 'b':
                result += f' **{element.text}** '
            case 'code':
                result += f'`{element.text}`'
            case None:
                result += element.text
    return result


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


def code_block(element: PageElement) -> str:
    pre = element.find('pre')
    code = pre.find('code')
    lang: str = code['class'][0]
    lang = lang.replace('language-', '')
    if lang == 'nasm':
        lang = 'x86asm'
    if lang == 'text':
        lang = 'bash'
    text: str = code.get_text()
    return "```" + lang + "\n" + text + ("" if text.endswith("\n") else "\n") + "```"


def toMarkdown(result: list, elements: Iterable[PageElement]):
    for element in elements:
        match element.name:
            case 'p':
                result.append("\n\n")
                result.append(paragraph(element))
            case 'a':
                result.append("\n\n" + link_card(element))
            case 'h2':
                result.append(f'\n\n## {paragraph(element)}')
            case 'h3':
                result.append(f'\n\n#### {paragraph(element)}')
            case 'blockquote':
                result.append("\n\n" + f'> {paragraph(element)}')
            case 'ul':
                result.append("\n\n" + unordered_list(element))
            case 'div':
                if element.attrs['class'][0] == 'highlight':
                    result.append("\n\n" + code_block(element))
            case 'figure':
                result.append("\n\n" + image(element))
            case None:
                result.append(element.text)


def article(soup: BeautifulSoup) -> str:
    jsinitdata = json.loads(soup.select(
        'script[id="js-initialData"]')[0].get_text())
    articles = jsinitdata["initialState"]["entities"]["articles"]
    inner = articles[list(articles.keys())[0]]

    created = inner["created"]
    updated = inner["updated"]
    return created, updated

# 知乎专栏


def column(soup: BeautifulSoup) -> str:
    jsinitdata = json.loads(soup.select(
        'script[id="js-initialData"]')[0].get_text())
    columns = jsinitdata["initialState"]["entities"]["columns"]
    inner = columns[list(columns.keys())[0]]

    created = inner["created"]
    updated = inner["updated"]
    return created, updated


def request(url: str):
    response = get(url)

    soup = BeautifulSoup(response.text, 'html.parser')

    title = soup.select('h1[class^="Post-Title"]')[0].text
    cover = soup.select("meta[property='og:image']")[0]['content']

    created, updated = article(soup)
    result = []
    body = soup.select('div[class^="RichText"]')[0].children

    toMarkdown(result, body)

    return "".join(result), cover, title, datetime.datetime.fromtimestamp(created), datetime.datetime.fromtimestamp(updated)


def main():
    cookie_text = '__snaker__id=5wtwqmPSk6Ny2utq; SESSIONID=iz59eiq3vrckOUMMIQwdOtprVYJVnHPWjNuaV5GLIA3; JOID=Vl4RAEqac2-8v_P6BJ1Eda1Ysa0coDxa3P2Tt2vwKRj_iYSgNAIfO9248_8BE88Nngi7pInOw_HY0H0Bvg50J8w=; osd=WlocA0iWd2K_vf_-CZ5GealVsq8QpDFZ3vGXumjyJRzyioasMA8cOdG8_vwDH8sAnQq3oITNwf3c3X4Dsgp5JM4=; _zap=23837413-994c-4340-95b4-2af240db134d; d_c0=AMCWuOFFUBiPTpy5Y4GgwgnPtHykVe5EWOQ=|1710483888; dream_token=ZWU3YjBhMDNkNmRkNGIwOTE3NGFmY2Y2ZWQ0MjQ2ZDUwNzkwOTcwNjdjODdjZjI4NjgxYTYzNmE2ZWIxYTFmNA==; _xsrf=ZR2fkCsyacR1j5pwcaRW761gCSyImHJs; __zse_ck=001_MO+AcSONgw5YH0=BcWBJabz8xAlKfXpXJQw8sRXLBvMIzfUfTWMxtwE9piYHKXBx=RjDrxWuW=RLMMjcNVWrviaEv4vmY+PMb+p+kJ9=gibj58ySDUCOHEuH53t/zM0S; ariawapChangeViewPort=false; ariaFixed=true; l_cap_id="OTM1NTYzMzllNTM3NGIyM2JlMmRmYTFjNmQ2MWEyOTY=|1716557820|a8fb7b7cdda4b191614481b9d40621acb6317e08"; r_cap_id="ZmZjZjFjYzE5ODYwNDkyMWI3ZDUxZThlZmJjMjBkNjI=|1716557820|3d651a6ec1dfb2a5e4265a62d28b37bbbb65ca0a"; cap_id="OGNiMWJkNTkzZjMxNDc1NTgyNmNmNjJmZWQ2ODM1NjM=|1716557820|aec9a50209e5ee2eed67d9f37d2cf066e5ddd07b"; ariaReadtype=1; ariaoldFixedStatus=false; ariaStatus=false; gdxidpyhxdE=X%5CfiCsSWZhSieDLXv%5Ct3AguRRrchW7jRrAM6BLavrsnBlxqEvhGPYi1OwoE%2FaN%2B3M%5CBpi%5CR%5C7NjoVpmJA0xmz4zwcMYA4de0eUDXZYp4RJo9Y%2BjGlcOzJRkt%2F%2F9BqBp83PlGi%2BsMA7%2BRxyaJacwORXqXPcomts0g5vEECoonQPUXjw64%3A1716559243514; captcha_session_v2=2|1:0|10:1716558652|18:captcha_session_v2|88:Zkd2NUNXUVdpN3E0ZmUyN1dlTVN4TjBhK0RvdlE4eitMVjl1Y1NDSGRSNVV6cDVKQTF5SjlVSUpPUC9oaG1USA==|11af66da98a81768f475a5558097a123c6391e27794a891f34172dab56190d2a; captcha_ticket_v2=2|1:0|10:1716558659|17:captcha_ticket_v2|728:eyJ2YWxpZGF0ZSI6IkNOMzFfdUxaMmYwXzF2cFFjeEszRndnRSowdktHTEhrQlc4RlJqaGlhQkdtYlk4NjhITVoySy5FMXJoYnpuVkVMZF9ic25iX3RlV1pFTldFaWQzTTQ0cmNDbTlfd0FUbHNKWGJZV1FGcFBtMEV3NnFTRG50d0lqeE4qOVRlQmtCblRmQnhQRmYwNXVJWG40WkV0MWdzTV9YOUNkWHJvTlhJeCpWZ0hxWVFhME45SnFYVzY0Qi5mdjYzbENOWURGSFlxRzRlZmxtQndOWVZ2SllPb2VVNUI4VnNSd0JIOGtTVFZTNklnSTl1Lmk1bm5jWXJSWllZZy5NSGp3YWhfOEtXXzVocFNubWUuYkUwZmVFbnlpMTlJUHd1M0ZfaGpEQkNoQVRMMlZTLm9kVFZVX3JDZHloZ3BTQnpSbkZSMnFoKlU1dm5tUUxRek9ONF9lcWVGRDJMaHAwRm12a3hCUDVnWXVWbUpJME1kRWtzMnB6S2NzUGg2UU5qVDVpTTBPSklvNlU5KnBPaklUT3FOYlZiV212Y0FWTGRYc0JOYk9jYU04dDBnQXpUU3FVTE9yZ3E4VGlMXzBjRllXc3ZYR1JkMWJRd2lyaFVjX1VkQ0tsc0xqZGp6S3ZXQk1DTXJaYUduNkRyWlZtR3d0Z0xfZ1hRbkpZbTJOeWQuNGdlOEhGWV9yc3g2elhoTFk3N192X2lfMSJ9|e0f868b2e2d47db698edafa7872c6b33a8923e0944e0ba99b01f86e89b5660b6; z_c0=2|1:0|10:1716558659|4:z_c0|92:Mi4xMEJmOU9RQUFBQUFBd0phNDRVVlFHQ1lBQUFCZ0FsVk5RLWs5WndDV1FRbFFKR0tXQWZyUENJeFdsUlpqRlgwWnBB|28319975d9abad2d2994a9c6e0c0033f965d4bf6fc3438e9b9c92e0ae52523c7; tst=r; Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49=1716466237,1716532982,1716544229,1716607619; Hm_lvt_bff3d83079cef1ed8fc5e3f4579ec3b3=1716466237,1716534406,1716550544,1716607826; Hm_lpvt_bff3d83079cef1ed8fc5e3f4579ec3b3=1716613494; KLBRSID=b33d76655747159914ef8c32323d16fd|1716614050|1716607812; Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49=1716614051; BEC=f3a75d7265fd269b7c515e5c94175904'

    for item in cookie_text.split('; '):
        key, value = item.split('=', 1)
        cookies[key] = value

    print("Cookies loaded successfully")

    current_dir = os.path.dirname(__file__)
    json_path = os.path.join(current_dir, 'map.json')
    map_json = json.loads(open(json_path, 'r').read())
    for url, value in map_json.items():
        urls_map[url] = url.replace(
            'https://zhuanlan.zhihu.com/p', "https://16bit-ykiko.github.io/about-me")

    for url in urls_map.keys():
        name = url.split('/')[-1]
        markdown, cover, title, cr, up = request(url)

        markdown = (f"---\n"
                    f"title: '{title}'\n"
                    f"date: {cr}\n"
                    f"updated: {up}\n"
                    f"type: 'post'\n"
                    f"cover: '{cover}'\n"
                    f"---\n") + markdown

        dest = os.path.join(current_dir, f'../hexo/source/_posts/{name}.md')

        with open(dest, 'w', encoding="utf-8") as f:
            f.write(markdown)

        print(f"Done: {name}")


if __name__ == '__main__':
    main()
