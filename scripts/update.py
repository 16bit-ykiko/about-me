import os
import json
import requests
from zhihu import Parser
from datetime import datetime

cookies = {}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}


def load_cookies():
    cookie_text = None

    if 'COOKIE_TEXT' in os.environ:
        cookie_text = os.environ['COOKIE_TEXT']
    else:
        raise Exception("COOKIE_TEXT not found")

    for item in cookie_text.split('; '):
        key, value = item.split('=', 1)
        cookies[key] = value

    print("Cookies loaded successfully")


def request(url: str):
    n = 0
    while n < 5:
        try:
            response = requests.get(
                url, timeout=10, headers=headers, cookies=cookies)
            response.raise_for_status()
            break
        except Exception as e:
            print(e)
            n += 1

    parser = Parser()
    article = parser.parse_article(response.text)
    created = datetime.fromtimestamp(article.created)
    updated = datetime.fromtimestamp(article.updated)
    result = (f"---\n"
              f"title: '{article.title}'\n"
              f"date: {created}\n"
              f"updated: {updated}\n"
              f"---\n\n") + article.content.dump()
    return result, article.cover


def download(url: str):
    n = 0
    while n < 5:
        try:
            response = requests.get(
                url, timeout=10, headers=headers)
            response.raise_for_status()
            break
        except Exception as e:
            print(e)
            n += 1

    return response.content


def main():
    load_cookies()
    path = os.path.dirname(__file__)
    urls = json.loads(open(os.path.join(path, 'urls.json'), 'r').read())

    for url, value in urls.items():
        urls[url] = url.replace('zhuanlan.zhihu.com/p',
                                "www.ykiko.me/articles")
    Parser.urls_map = urls

    for url, value in urls.items():
        name = url.split('/')[-1]
        markdown, cover = request(url)

        dir = os.path.join(path, f'../website/content/articles/{name}')
        if not os.path.exists(dir):
            os.makedirs(dir)

        with open(os.path.join(dir, 'index.md'), 'w', encoding="utf-8") as f:
            f.write(markdown)

        with open(os.path.join(dir, 'featured.png'), 'wb') as f:
            f.write(download(cover))

        print(f"Done: {name}")


if __name__ == "__main__":
    main()
