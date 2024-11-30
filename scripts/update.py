import os
import cv2
import time
import random
import requests
import numpy as np
from zhihu import Parser

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException


def click(driver, xpath):
    button = driver.find_element(By.XPATH, xpath)
    actions = ActionChains(driver)
    actions.move_to_element(button)
    actions.click(button)
    actions.perform()
    time.sleep(random.uniform(1.3, 1.5))


def input(driver, name, text):
    input_elem = driver.find_element(By.NAME, name)

    action = ActionChains(driver)
    action.move_to_element(input_elem)
    action.click(input_elem)
    action.perform()
    time.sleep(random.uniform(0.3, 0.5))

    input_elem.clear()
    time.sleep(random.uniform(0.3, 0.5))

    for char in text:
        input_elem.send_keys(char)
        time.sleep(random.uniform(0.1, 0.3))

    time.sleep(random.uniform(0.3, 0.5))


def locate(slider_img, background_img):
    # 分离滑块图像的 BGR 和 Alpha 通道
    bgr = slider_img[:, :, :3]
    alpha = slider_img[:, :, 3]

    # 创建掩码，alpha 值大于 1 的部分为有效区域
    _, mask = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)

    # 图像预处理：增强对比度和清晰度

    # 将滑块图像转为灰度图像
    slider_image_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 使用 Canny 边缘检测增强图像轮廓
    slider_edges = cv2.Canny(slider_image_gray, 100, 200)

    # 背景图像模糊
    background_image_blur = cv2.GaussianBlur(
        background_img, (5, 5), 0)

    # 使用 Canny 边缘检测提取背景的轮廓
    background_edges = cv2.Canny(background_image_blur, 100, 200)

    # 使用模板匹配来查找滑块的位置，考虑掩码（仅匹配非透明区域）
    result = cv2.matchTemplate(
        background_edges, slider_edges, cv2.TM_CCOEFF_NORMED, mask=mask)

    # 获取匹配结果中最强的匹配位置
    _, _, _, max_loc = cv2.minMaxLoc(result)

    return max_loc


def verify(driver: webdriver.Chrome, n=5):
    try:
        slider = driver.find_element(By.XPATH, '//img[@alt="验证码滑块"]')
        background = driver.find_element(By.XPATH, '//img[@alt="验证码背景"]')

        def download_to_cv2(url):
            response = requests.get(url)
            img = cv2.imdecode(np.frombuffer(
                response.content, np.uint8), cv2.IMREAD_UNCHANGED)
            return img

        slider_img = download_to_cv2(slider.get_attribute('src'))
        background_img = download_to_cv2(background.get_attribute('src'))
        loc = locate(slider_img, background_img)

        print(f"shown slider image.shape: {slider.size}")
        print(f"shown background image.shape: {background.size}")
        print(f"target location: {loc}")
        print(f"raw background image.shape: {background_img.shape}")

        scale = background.size['width'] / background_img.shape[1]
        distance = loc[0] * scale + slider.size['width'] / 4
        print(f"distance: {distance}")

        action = ActionChains(driver)
        action.click_and_hold(slider)
        remaining_distance = distance
        while remaining_distance > 0:
            scale = random.uniform(0.1, 0.3)
            move_distance = scale * distance
            if move_distance > remaining_distance:
                move_distance = remaining_distance
            action.move_by_offset(move_distance, 0)
            remaining_distance -= move_distance
        action.release()
        action.perform()

    except Exception as e:
        print(e)
        if n > 0:
            verify(driver, n-1)
        else:
            print("Failed to verify")


def login(driver: webdriver.Chrome):
    # 点击使用密码登录
    click(driver, "//*[text()='密码登录']")
    import json
    data = json.load(os.environ['PASSWORD'])

    # 输入用户名
    input(driver, 'username', data['username'])
    input(driver, 'password', data['password'])

    # 点击登录
    click(driver, "//*[text()='登录' and not(text()='密码登录')]")

    # 验证
    verify(driver)


def parse(text: str, series: tuple[str, int] | None = None):
    from datetime import datetime

    parser = Parser()
    article = parser.parse_article(text)
    created = datetime.fromtimestamp(article.created)
    updated = datetime.fromtimestamp(article.updated)

    result = (f"---\n"
              f"title: '{article.title}'\n"
              f"date: {created}\n"
              f"updated: {updated}\n")

    if series:
        result += (f"series: ['{series[0]}']\n"
                   f"series_order: {series[1]}\n")

    result += f"---\n\n" + article.content.dump()
    return result, article.cover


def main():
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    # 连接到从命令行启动的浏览器
    driver = webdriver.Chrome(options=options)
    driver.get("https://www.zhihu.com/signin")

    # 尝试登录
    try:
        driver.find_element(By.XPATH, "//a[text()='首页']")
        print("Already logged in")
    except NoSuchElementException as e:
        print("Not logged in, trying to login")
        login(driver)

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
        driver.get(url)

        try:
            markdown, cover = parse(driver.page_source, article.series)
        except Exception as e:
            print(f"Failed to parse {name}: {e}")
            continue

        dir = os.path.join(path, f'../website/content/zh-cn/articles/{name}')
        if not os.path.exists(dir):
            os.makedirs(dir)

        with open(os.path.join(dir, 'index.md'), 'w', encoding="utf-8") as f:
            f.write(markdown)

        if cover:
            with open(os.path.join(dir, 'featured.png'), 'wb') as f:
                driver.get(cover)
                f.write(driver.page_source.encode('utf-8'))

        # time.sleep(random.choice([1, 2, 3, 4]))

        print(f"Done: {name}")


if __name__ == '__main__':
    main()
