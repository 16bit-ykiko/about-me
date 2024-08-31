import os
import time
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


def request(url: str, series: tuple[str, int] | None = None):
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
              f"updated: {updated}\n")

    if series is not None:
        result += (f"series: ['{series[0]}']\n"
                   f"series_order: {series[1]}\n")

    result += f"---\n\n" + article.content.dump()

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
    import articles

    urls = {}
    for article in articles.all:
        urls[article.url] = article.url.replace('zhuanlan.zhihu.com/p',
                                                "www.ykiko.me/zh-cn/articles")
    Parser.urls_map = urls

    for article in articles.all:
        url = article.url
        name = url.split('/')[-1]
        markdown, cover = request(url, article.series)

        dir = os.path.join(path, f'../website/content/zh-cn/articles/{name}')
        if not os.path.exists(dir):
            os.makedirs(dir)

        with open(os.path.join(dir, 'index.md'), 'w', encoding="utf-8") as f:
            f.write(markdown)

        if cover:
            with open(os.path.join(dir, 'featured.png'), 'wb') as f:
                f.write(download(cover))

        time.sleep(2)

        print(f"Done: {name}")


if __name__ == "__main__":
    main()
