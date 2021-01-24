import asyncio
import base64
import os

import pyperclip as pyperclip
from PIL import Image
from pyppeteer import launch


async def main(blog_name):
    """
    :param blog_name: 博客名字，自己博客主页url的最后部分
    :return:
    """
    browser = await launch(devtools=True, dumpio=True, autoClose=True,
                           args=['--start-maximized',  # 设置浏览器全屏
                                 '--no-sandbox',  # 取消沙盒模式，沙盒模式下权限太小
                                 '--disable-infobars',  # 关闭受控制提示
                                 # 设置ua
                                 '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3542.0 Safari/537.36'
                                 ],
                           userDataDir=os.path.abspath('./cookies'))
    print(await browser.userAgent())
    pages_list = await browser.pages()
    page = pages_list[0]
    # await page.setViewport(viewport={'width': 1920, 'height': 1080})
    # 打开博客主页
    await page.goto('https://blog.csdn.net/%s' % blog_name)
    await page.waitFor(1000)
    # 先找到已有文章
    elements = await page.querySelectorAll('#articleMeList-blog > div.article-list > div')
    article_list = []
    for i in range(1, len(elements) + 1):
        article = await page.querySelector('#articleMeList-blog > div.article-list > div:nth-child(%d) > h4 > a' % i)
        article = await (await article.getProperty('textContent')).jsonValue()
        article_list.append(str(article).strip('\n').split('\n')[1].strip())
    print('已有文章%d篇: ' % len(article_list), article_list)
    # 点击 创作中心
    await page.click(
        '#csdn-toolbar > div > div > div.toolbar-container-right > div > div.toolbar-btn.toolbar-btn-write.csdn-toolbar-fl > a')
    await page.waitFor(4000)
    if '登录' in await page.title():
        await login(page)
    # 等待登录成功，最多等5分钟
    await page.waitForSelector(
        '#view-containe > div.left_box > div.left_box_top > a.routerlink-bt.routerlink-bt-md > span',
        timeout=300 * 1000)
    print('已登录')
    # 点击 Markdown 编辑器
    await page.click('#view-containe > div.left_box > div.left_box_top > a.routerlink-bt.routerlink-bt-md > span')
    await page.waitFor(3000)
    # 切换到写文章页签
    pages_list = await browser.pages()
    page = pages_list[-1]
    # 开始写文章
    url_list = []
    for title, content, tags, category in get_local_articles():
        if title in article_list:
            continue
        url = await write_article(page, title, content, tags, category)
        url_list.append(url)
        # 点击 再写一篇
        await page.click('#alertSuccess > div > div.pos-top > div:nth-child(4) > div.btn-new.c-blue.underline > span')
        await page.waitFor(3000)
    await browser.close()
    print('本次共发布%d篇文章，等待平台审核' % len(url_list))


async def login(page):
    print('正在登录...')
    # 点击 CSDN App扫码
    await page.click('#app > div > div > div.main > div.main-login > div.main-select > ul > li:nth-child(1) > a')
    # 获取登录二维码
    img_element = await page.querySelector('#appqr > span.app-code-wrap > img')
    img_src = await (await img_element.getProperty('src')).jsonValue()
    img_src = str(img_src).split(',')[1]
    img_data = base64.b64decode(img_src)
    img_name = 'login.png'
    if os.path.exists(img_name):
        os.remove(img_name)
    with open(img_name, 'wb') as f:
        f.write(img_data)
    img = Image.open(img_name)
    img.show()


async def write_article(page, title, content, tags, category):
    """
    :param page: 写文章页签
    :param title: 文章标题
    :param content: 文章内容
    :param tags: 标签，多个用英文","隔开
    :param category: 分类
    :return: 发布文章的地址
    """
    # 选中标题输入框
    print('输入标题: %s' % title)
    title_input = await page.querySelector(
        'body > div.app.app--light > div.layout > div.layout__panel.layout__panel--articletitle-bar > div > div.article-bar__input-box > input')
    # 清空原有内容
    await title_input.focus()
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyA')
    await page.keyboard.up('Control')
    await page.keyboard.up('Backspace')
    # 输入标题内容
    await title_input.type(title)
    # 选中文章输入框
    print('输入文章内容: %s...' % content[:20])
    content_input = await page.querySelector(
        'body > div.app.app--light > div.layout > div.layout__panel.flex.flex--row > div > div.layout__panel.flex.flex--row > div.layout__panel.layout__panel--editor > div.editor > pre')
    # 清空原有内容
    await content_input.focus()
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyA')
    await page.keyboard.up('Control')
    await page.keyboard.up('Backspace')
    # 输入文章内容
    # await content_input.type(content)
    # 先复制到剪切板，再 Ctrl + V 粘贴，加快速度
    pyperclip.copy(content)
    await content_input.focus()
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyV')
    await page.keyboard.up('Control')
    # 多等一会儿，csdn加载图床
    await page.waitFor(5000)
    # 点击 发布文章
    await page.click(
        'body > div.app.app--light > div.layout > div.layout__panel.layout__panel--articletitle-bar > div > div.article-bar__user-box.flex.flex--row > button.btn.btn-publish')
    # 删除原来的标签，如果有的话
    exist_tags = await page.querySelectorAll(
        'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__content > div:nth-child(3) > div > div > div > span > span > i')
    for i in exist_tags:
        # 每删一个，页面会有变化
        tag = await page.querySelector(
            'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__content > div:nth-child(3) > div > div > div > span > span > i')
        await tag.click()
        await page.waitFor(500)
    # 点击 添加文章标签
    print('添加标签: %s' % tags)
    add_tag = await page.querySelector(
        'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__content > div:nth-child(3) > div > div > div > button')
    await add_tag.click()
    # 添加标签
    tag_input = await page.querySelector(
        'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__content > div:nth-child(3) > div > div > div.mark_selection_box > div.mark_selection_box_header > div > div.el-input.el-input--suffix > input')
    tag_list = tags.split(',')
    for tag in tag_list:
        await tag_input.type(tag.strip())
        await page.waitFor(500)
        await page.keyboard.press('Enter')
        await page.waitFor(500)
    # 收起 添加文章标签
    await add_tag.click()
    # 添加分类
    print('添加分类: %s' % category)
    add_category = await page.querySelector('#tagList > button')
    await add_category.click()
    category_input = await page.querySelector(
        'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__content > div:nth-child(4) > div > div > input')
    await category_input.type(category)
    await page.waitFor(500)
    await page.keyboard.press('Enter')
    await page.waitFor(500)
    # 选择文章类型：原创
    print('文章类型: 原创')
    select_box = await page.querySelector(
        'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__content > div.inline-box > div > div')
    await select_box.click()
    await page.waitFor(500)
    # 下拉框的 id 是个随机值，每次都不一样，通过按键曲线救国
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    # 选择发布形式：公开 2, 私密 4, 粉丝可见 6, VIP可见 8
    print('发布形式: 公开')
    flag = 2
    await page.click(
        'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__content > div.form-entry.flex.form-entry__field-switch-box.overflow-unset.form-entry-marginBottom > div > div > label:nth-child(%d)' % flag)
    # 发布文章：保存为草稿 btn-c-blue, 发布文章 btn-b-red
    print('点击发布...')
    flag = 'btn-b-red'
    await page.click(
        'body > div.app.app--light > div.modal > div > div.modal__inner-2 > div.modal__button-bar > button.button.%s' % flag)
    await page.waitFor(3000)
    url_element = await page.querySelector('#alertSuccess > div > div.pos-top > div:nth-child(4) > a')
    url = await (await url_element.getProperty('href')).jsonValue()
    print('发布成功, 文章地址: %s' % url)
    return url


def get_local_articles():
    for file in os.listdir(ARTICLE_PATH):
        if file in IGNORE_LIST:
            continue
        if file.endswith('.md'):
            try:
                with open(os.path.join(ARTICLE_PATH, file), 'r', encoding='utf-8') as text:
                    readlines = text.readlines()
                    title = readlines[1].strip('title:').strip()
                    tags = readlines[3].strip('tags:').strip().strip('[').strip(']')
                    category = readlines[4].strip('categories:').strip()
                    content = ''.join(readlines[7:])
                    yield title, content, tags, category
            except Exception as e:
                print('文章标题、标签、分类信息读取有误：%s' % file, str(e))


ARTICLE_PATH = 'E:/Markdown'
IGNORE_LIST = ['欢迎使用Markdown编辑器.md']
blog_name = 'yushuaigee'
asyncio.get_event_loop().run_until_complete(main(blog_name))
