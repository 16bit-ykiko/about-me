import os
import json

from .request import get
from .parse import toMarkdown, urls_map

from bs4 import BeautifulSoup
from datetime import datetime


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
    body = soup.select('div[class^="RichText"]')[0]
    result = toMarkdown(body)

    return "".join(result), cover, title, datetime.fromtimestamp(created), datetime.fromtimestamp(updated)


def load_urls_map():
    current_dir = os.path.dirname(__file__)
    json_path = os.path.join(current_dir, 'map.json')
    map_json = json.loads(open(json_path, 'r').read())
    for url, value in map_json.items():
        urls_map[url] = url.replace(
            'https://zhuanlan.zhihu.com/p', "https://16bit-ykiko.github.io/about-me")

    print("Urls map loaded successfully")


def main():
    current_dir = os.path.dirname(__file__)
    load_urls_map()

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
