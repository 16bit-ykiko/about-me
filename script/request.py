import os
import requests

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


def get(url: str):

    if not cookies:
        load_cookies()

    n = 0
    while n < 5:
        try:
            return requests.get(
                url, timeout=10, headers=headers, cookies=cookies)
        except Exception as e:
            print(e)
            n += 1
