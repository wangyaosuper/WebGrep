
import sys
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time
import random
import plistlib
import base64
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def extract_links_from_file(filename):
    """从文件中提取所有URL链接"""
    # 检查文件扩展名
    if filename.endswith('.webarchive'):
        # 处理webarchive文件
        return extract_links_from_webarchive(filename)
    else:
        # 处理普通文本文件
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        # 使用正则表达式提取URL
        url_pattern = r'https?://[^\s<>"{}|\^`\[\]]+'
        links = re.findall(url_pattern, content)

        return list(set(links))  # 去重

def extract_news_from_autohome_list(html_content):
    """从autohome新闻列表页提取新闻信息"""
    soup = BeautifulSoup(html_content, 'html.parser')
    news_list = []

    # 查找所有包含h2标签的li元素
    all_li = soup.find_all('li')
    news_items = [li for li in all_li if li.find('h2')]

    # 使用集合来去重
    seen_urls = set()

    # 定义需要排除的标题关键词
    excluded_title_keywords = [
        '发布作品', '找论坛', '登录', '注册', '更多',
        '移动App', '触屏版', '小程序', 'i车商', '本地服务',
        '下载App', '选择城市', '搜索', '点赞', '评论',
        '收藏', '分享', '问编辑', '当前位置', '首页',
        '车闻中心', '人物对话', '正文', '关注', '原创',
        '浏览', '所有标签', '试试其他标签', '商业模式',
        '新车预告', '整车', '企业/品牌事件', '海外售价',
        '生产研发', '企业财报', '企业营收', '配置/售价调整',
        '行业视角'
    ]

    for item in news_items:
        try:
            # 查找h2标签中的链接（这是新闻标题链接）
            h2_tag = item.find('h2')
            if not h2_tag:
                continue

            link_tag = h2_tag.find('a', href=True)
            if not link_tag:
                continue

            url = link_tag['href']
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('http'):
                continue

            # 检查URL是否符合autohome新闻链接的模式
            # 应该是 /news/年月/数字.html 的格式
            if not re.search(r'/news/\d{6}/\d+\.html', url):
                continue

            # 去重
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 提取标题
            title = link_tag.get_text().strip()

            # 检查标题是否包含排除的关键词
            if any(keyword in title for keyword in excluded_title_keywords):
                continue

            # 检查标题长度，太短的可能是导航或功能按钮
            if len(title) < 10:
                continue

            # 查找摘要（在p标签中）
            summary = ""
            p_tag = item.find('p')
            if p_tag:
                summary = p_tag.get_text().strip()

            # 查找时间（通常在p标签中包含日期）
            news_time = "未知时间"
            if p_tag:
                # 尝试从摘要中提取日期
                date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', summary)
                if date_match:
                    news_time = date_match.group(1)

            news_list.append({
                'title': title or "未知标题",
                'time': news_time,
                'url': url,
                'content': summary or "无摘要"
            })
        except Exception as e:
            print(f"提取新闻时出错: {str(e)}")
            continue

    return news_list

def is_news_link(url):
    """判断URL是否是新闻文章链接"""
    url_lower = url.lower()

    # 排除图片、CSS、JavaScript等资源链接
    excluded_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.webp', '.avif']
    for ext in excluded_extensions:
        if url_lower.endswith(ext):
            return False

    # 排除静态资源路径
    excluded_paths = ['/static/', '/assets/', '/images/', '/img/', '/css/', '/js/', '/thumbnail/', '/uploads/']
    for path in excluded_paths:
        if path in url_lower:
            return False

    # 排除包含特定查询参数的链接
    excluded_params = ['format=jpg', 'format=png', 'format=gif', 'format=svg', 'format=webp', 'format=avif', 'x-bce-process=image']
    for param in excluded_params:
        if param in url_lower:
            return False

    # 排除明显的资源域名
    excluded_domains = ['img.', 'image.', 'static.', 'assets.', 'cdn.', 'hm.baidu.com']
    for domain in excluded_domains:
        if domain in url_lower:
            # 检查是否在域名部分（在第一个/之前）
            url_without_protocol = url_lower.split('://')[-1] if '://' in url_lower else url_lower
            first_slash_pos = url_without_protocol.find('/')
            domain_part = url_without_protocol[:first_slash_pos] if first_slash_pos != -1 else url_without_domain
            if domain in domain_part:
                return False

    # 排除非新闻链接的路径
    excluded_paths_news = ['/tougao/', '/?page=', '/register', '/login', '/search', '/icp.html', '/homepage', '/dd_number/', '/special/', '/special_category/', '/creator/', '/new-tech/C-', '/mikecrm.com/']
    for path in excluded_paths_news:
        if path in url_lower:
            return False

    # 排除以数字结尾的jspx文件（通常是分类页面）
    if re.search(r'/\d+\.jspx$', url_lower):
        return False

    # 排除备案信息网站
    excluded_sites = ['beian.miit.gov.cn', 'beian.gov.cn']
    for site in excluded_sites:
        if site in url_lower:
            return False

    # 排除首页链接（以/结尾或没有路径）
    if url_lower.endswith('/') or re.search(r'https?://[^/]+/?$', url_lower):
        return False

    # 针对autohome网站的特殊处理
    if 'autohome.com.cn' in url_lower:
        # autohome的新闻链接模式：/news/年月/数字.html
        # 例如：/news/202604/1314001.html
        if re.search(r'/news/\d{6}/\d+\.html', url_lower):
            return True
        # 排除其他autohome链接（如分类页、列表页等）
        # 例如：/news/1/、/news/2/、/51/0/1/conjunction.html等
        if re.search(r'/news/\d+/?$', url_lower) or re.search(r'/\d+/\d+/\d+/', url_lower):
            return False
        # 排除包含特定路径的autohome链接
        if any(path in url_lower for path in ['/bestauto/', '/chejiahao/', '/v.', '/hangye/list/']):
            return False

    # 只保留看起来像新闻文章的链接
    # 新闻链接通常包含数字或特定的路径模式
    # 检查URL是否包含数字，这通常是新闻文章的特征
    if re.search(r'/\d+', url_lower):
        return True

    # 如果URL包含常见的新闻路径模式，也认为是新闻链接
    news_paths = ['/news/', '/article/', '/post/', '/story/', '/detail/', '/view/']
    for path in news_paths:
        if path in url_lower:
            return True

    # 其他情况不认为是新闻链接
    return False

def extract_links_from_webarchive(filename):
    """从webarchive文件中提取所有URL链接"""
    try:
        with open(filename, 'rb') as f:
            plist = plistlib.load(f)

        links = []
        is_autohome_list = False

        # 获取主URL
        if 'WebMainResource' in plist:
            if 'WebResourceURL' in plist['WebMainResource']:
                main_url = plist['WebMainResource']['WebResourceURL']
                links.append(main_url)

                # 检查是否是autohome新闻列表页
                if 'autohome.com.cn/news/' in main_url:
                    is_autohome_list = True

        # 获取子资源中的URL
        if 'WebSubresources' in plist:
            for resource in plist['WebSubresources']:
                if 'WebResourceURL' in resource:
                    links.append(resource['WebResourceURL'])

        # 从HTML内容中提取更多链接
        if 'WebMainResource' in plist and 'WebResourceData' in plist['WebMainResource']:
            try:
                data = plist['WebMainResource']['WebResourceData']
                if isinstance(data, bytes):
                    # 尝试解码
                    try:
                        html_content = data.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            html_content = data.decode('gbk')
                        except UnicodeDecodeError:
                            html_content = data.decode('latin-1')

                    # 如果是autohome新闻列表页，直接提取新闻信息
                    if is_autohome_list:
                        print("检测到autohome新闻列表页，直接提取新闻信息...")
                        news_list = extract_news_from_autohome_list(html_content)
                        if news_list:
                            # 将新闻信息保存到work目录
                            work_dir = "work"
                            if not os.path.exists(work_dir):
                                os.makedirs(work_dir)
                            output_file = os.path.join(work_dir, f"autohome_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                            save_news_to_file(news_list, output_file)
                            print(f"已从autohome新闻列表页提取 {len(news_list)} 条新闻并保存到 {output_file}")
                        # 同时也提取链接，保持原有功能
                        soup = BeautifulSoup(html_content, 'html.parser')
                        for a_tag in soup.find_all('a', href=True):
                            href = a_tag['href']
                            # 处理不同类型的链接
                            if href.startswith('http'):
                                links.append(href)
                            elif href.startswith('//'):
                                # 处理以//开头的协议相对链接
                                links.append('https:' + href)
                            elif href.startswith('/') and not href.startswith('//'):
                                # 处理以/开头的绝对路径链接
                                base_url = plist['WebMainResource']['WebResourceURL']
                                parsed = base_url.split('/')
                                if len(parsed) >= 3:
                                    links.append(f"{parsed[0]}//{parsed[2]}{href}")
                    else:
                        # 非autohome新闻列表页，使用原有逻辑
                        soup = BeautifulSoup(html_content, 'html.parser')
                        for a_tag in soup.find_all('a', href=True):
                            href = a_tag['href']
                            # 处理不同类型的链接
                            if href.startswith('http'):
                                links.append(href)
                            elif href.startswith('//'):
                                # 处理以//开头的协议相对链接
                                links.append('https:' + href)
                            elif href.startswith('/') and not href.startswith('//'):
                                # 处理以/开头的绝对路径链接
                                base_url = plist['WebMainResource']['WebResourceURL']
                                parsed = base_url.split('/')
                                if len(parsed) >= 3:
                                    links.append(f"{parsed[0]}//{parsed[2]}{href}")
            except Exception as e:
                print(f"解析HTML内容时出错: {str(e)}")

        # 过滤链接，只保留新闻文章链接
        filtered_links = [link for link in links if is_news_link(link)]

        return list(set(filtered_links))  # 去重
    except Exception as e:
        print(f"解析webarchive文件时出错: {str(e)}")
        return []

def extract_news_content(url):
    """从新闻URL中提取标题、时间和正文内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        # 检查是否是gasgoo网站
        is_gasgoo = 'gasgoo.com' in url.lower()

        # 检查是否是autohome网站
        is_autohome = 'autohome.com.cn' in url.lower()

        # 检查是否是autor网站
        is_autor = 'autor.com.cn' in url.lower()

        # 尝试提取标题
        title = None
        if is_autohome:
            # autohome网站的标题提取逻辑
            # 首先尝试从meta标签中提取标题
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                title = meta_title['content'].strip()

            # 如果没有从meta标签获取到标题，尝试从h1标签提取
            if not title:
                h1_tags = soup.find_all('h1')
                if h1_tags:
                    # 过滤掉明显不是新闻标题的元素
                    for h1_tag in h1_tags:
                        title_text = h1_tag.get_text().strip()
                        # 跳过明显不是新闻标题的元素
                        # 增加更多过滤关键词，包括导航、功能按钮等非新闻内容
                        excluded_keywords = [
                            '发布作品', '找论坛', '数据分析', '新车上市/价格',
                            '登录', '注册', '更多', '移动App', '触屏版',
                            '小程序', 'i车商', '本地服务', '下载App',
                            '选择城市', '搜索', '点赞', '评论', '收藏',
                            '分享', '问编辑', '当前位置', '首页', '车闻中心',
                            '人物对话', '正文', '关注', '原创', '浏览',
                            '所有标签', '试试其他标签', '商业模式', '新车预告',
                            '整车', '企业/品牌事件', '海外售价', '生产研发',
                            '企业财报', '企业营收', '配置/售价调整', '行业视角',
                            '全部车系', '全部地区', '全部主题', '摩托车论坛',
                            '资讯文章', '最新', '车闻', '导购', '试驾评测',
                            '用车', '文化', '游记', '技术', '改装赛事',
                            '新能源', '行业', '全部', '行业动态', '热点追踪',
                            '车闻轶事', '国产新车', '进口新车', '召回碰撞',
                            '市场分析', '用户调研', '高端对话', '零部件',
                            '智能网联', '行业政策', '整车', '新能源', '后市场',
                            '热门文章', '精彩分类', '编辑博客', '合作媒体报道'
                        ]
                        # 检查标题是否包含排除的关键词
                        if title_text and len(title_text) > 10 and not any(keyword in title_text for keyword in excluded_keywords):
                            # 额外检查：如果标题包含多个排除关键词，说明是导航内容
                            nav_count = sum(1 for keyword in excluded_keywords if keyword in title_text)
                            if nav_count == 0:
                                title = title_text
                                break

            # 如果没有找到标题，尝试其他选择器
            if not title:
                title_selectors = ['.article-title', '.news-title', '.title', 'h2']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title_text = title_elem.get_text().strip()
                        # 再次检查标题是否包含排除的关键词
                        excluded_keywords = [
                            '发布作品', '找论坛', '登录', '注册', '更多',
                            '移动App', '触屏版', '小程序', 'i车商', '本地服务',
                            '下载App', '选择城市', '搜索', '点赞', '评论',
                            '收藏', '分享', '问编辑', '当前位置', '首页',
                            '车闻中心', '人物对话', '正文', '关注', '原创',
                            '浏览', '所有标签', '试试其他标签', '商业模式',
                            '新车预告', '整车', '企业/品牌事件', '海外售价',
                            '生产研发', '企业财报', '企业营收', '配置/售价调整',
                            '行业视角', '全部车系', '全部地区', '全部主题',
                            '摩托车论坛', '资讯文章', '最新', '车闻', '导购',
                            '试驾评测', '用车', '文化', '游记', '技术',
                            '改装赛事', '新能源', '行业', '全部', '行业动态',
                            '热点追踪', '车闻轶事', '国产新车', '进口新车',
                            '召回碰撞', '市场分析', '用户调研', '高端对话',
                            '零部件', '智能网联', '行业政策', '整车',
                            '新能源', '后市场', '热门文章', '精彩分类',
                            '编辑博客', '合作媒体报道'
                        ]
                        if title_text and len(title_text) > 5 and not any(keyword in title_text for keyword in excluded_keywords):
                            title = title_text
                            break
                        else:
                            title = None

            # 对于autohome网站，如果标题为空或未知，则跳过这条新闻
            if not title or title == "未知标题":
                return None
        elif is_gasgoo:
            # gasgoo网站使用h1标签作为标题
            title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text().strip()
            # 如果没有找到标题，尝试其他选择器
            if not title:
                title_selectors = ['.article-title', '.news-title', '.title', 'h2']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text().strip()
                        if title and len(title) > 5:  # 确保标题有一定长度
                            break
        else:
            # 其他网站的标题提取逻辑
            # 首先尝试从页面内容中查找标题
            # 查找包含日期的元素，然后获取其后的文本作为标题
            date_pattern = r'\d{4}-\d{2}-\d{2}'
            for elem in soup.find_all(string=re.compile(date_pattern)):
                parent = elem.parent
                if parent and 'tt1' in parent.get('class', []):
                    # 找到日期元素后，获取其后的兄弟元素中的文本作为标题
                    next_sibling = parent.find_next_sibling()
                    if next_sibling:
                        title = next_sibling.get_text().strip()
                        if title:
                            break

            # 如果没有找到标题，尝试使用标准选择器
            if not title:
                title_selectors = ['h1', 'h2', '.title', '#title', '.article-title', '.news-title', '[class*="title"]']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text().strip()
                        if title:
                            break

        # 尝试提取时间
        time_elem = None
        time_selectors = [
            '.time', '.date', '.publish-time', '.article-time', 
            '.news-time', '[class*="time"]', '[class*="date"]',
            'time', '.post-time', '.pub-time'
        ]
        for selector in time_selectors:
            time_elem = soup.select_one(selector)
            if time_elem:
                break

        news_time = "未知时间"
        if is_autor:
            # autor网站的时间在.tt1类的span标签中
            tt1_elem = soup.find('span', class_='tt1')
            if tt1_elem:
                time_text = tt1_elem.get_text().strip()
                # 提取日期时间部分（格式：智驾网 2025-12-16 15:34）
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', time_text)
                if date_match:
                    news_time = date_match.group(1)
        elif is_autohome:
            # autohome网站的时间提取逻辑
            # 查找包含日期的元素
            date_pattern = r'\d{4}-\d{2}-\d{2}'
            for elem in soup.find_all(string=re.compile(date_pattern)):
                parent = elem.parent
                if parent:
                    # 检查是否是文章发布时间
                    parent_text = parent.get_text().strip()
                    if re.search(date_pattern, parent_text):
                        news_time = parent_text.strip()
                        break
        elif is_gasgoo:
            # gasgoo网站的时间在.userInfo div中的span标签里
            user_info = soup.find('div', class_='userInfo')
            if user_info:
                time_span = user_info.find('span')
                if time_span:
                    news_time = time_span.get_text().strip()
            # 如果没有找到时间，尝试其他选择器
            if news_time == "未知时间":
                time_selectors = ['.time', '.date', '.publish-time', '.article-time', '.news-time', 'time']
                for selector in time_selectors:
                    time_elem = soup.select_one(selector)
                    if time_elem:
                        time_text = time_elem.get_text().strip()
                        # 验证时间格式（包含年月日）
                        if re.search(r'\d{4}-\d{2}-\d{2}', time_text):
                            news_time = time_text
                            break
        else:
            news_time = time_elem.get_text().strip() if time_elem else "未知时间"

        # 尝试提取正文内容
        content = None
        if is_autohome:
            # autohome网站的内容提取逻辑
            # 查找文章内容区域
            content_selectors = [
                '#articlewrap', '.article-content', '#content',
                '.content', '.article-body', '#article-content',
                '.article-text', '.news-content', '#article-text'
            ]
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 移除脚本和样式标签
                    for script in content_elem(["script", "style"]):
                        script.extract()

                    # 定义需要移除的class和id
                    remove_selectors = [
                        '.nav', '.navigation', '.header', '.footer', 
                        '.sidebar', '.related', '.recommend', '.tags',
                        '.author-info', '.share', '.comment', '.ad',
                        '#footer', '#header', '#nav', '#sidebar',
                        '.article-tags', '.article-footer', '.related-news',
                        '.author-works', '.enter-homepage', '.related-videos',
                        '.forum-recommend', '.q-and-a', '.download-app'
                    ]

                    # 移除不需要的元素
                    for remove_selector in remove_selectors:
                        for elem in content_elem.select(remove_selector):
                            elem.extract()

                    content = content_elem.get_text(separator='\n').strip()
                    # 验证内容有效性
                    if content and len(content) > 100:
                        # 先移除开头的导航信息
                        # 查找正文开始的位置（遇到"正文"或"关注"等标识）
                        content_start = 0
                        for keyword in ['正文', '关注', '原创', '浏览']:
                            pos = content.find(keyword)
                            if pos != -1 and pos > content_start:
                                content_start = pos
                        # 如果找到了正文开始标识，截取从该位置开始的内容
                        if content_start > 0:
                            content = content[content_start:].strip()
                        # 检查内容是否包含大量导航文本（非新闻内容）
                        nav_keywords = ['登录', '注册', '发布作品', '找论坛', '下载App', 
                                      '小程序', '移动App', '触屏版', 'i车商', '本地服务',
                                      '选择城市', '搜索', '点赞', '评论', '收藏', '分享',
                                      '所有标签', '试试其他标签', '商业模式', '新车预告',
                                      '当前位置', '首页', '车闻中心', '人物对话', '正文',
                                      '关注', '原创', '浏览', '全部车系', '全部地区',
                                      '全部主题', '摩托车论坛', '资讯文章', '最新', '车闻',
                                      '导购', '试驾评测', '用车', '文化', '游记', '技术',
                                      '改装赛事', '新能源', '行业', '全部', '行业动态',
                                      '热点追踪', '车闻轶事', '国产新车', '进口新车',
                                      '召回碰撞', '市场分析', '用户调研', '高端对话',
                                      '零部件', '智能网联', '行业政策', '整车', '后市场',
                                      '热门文章', '精彩分类', '编辑博客', '合作媒体报道']

                        # 增加底部推荐内容的过滤关键词
                        footer_keywords = [
                            '文章标签', '向编辑', '询底价',
                            '作者其他作品',
                            '进入主页', '相关视频', '论坛推荐',
                            '大家都在问', '扫码下载汽车之家App',
                            '京公网安备', '京ICP备', '信息网络传播视听节目许可证',
                            '广播电视节目制作经营许可证', '中央网信办',
                            '违法和不良信息举报中心', '举报电话', '举报邮箱', '隐私协议',
                            '万 播放', 
                            'www.autohome.com.cn', 
                            '公司名称：北京车之家信息技术有限公司',
                            '©', '京公网安备',
                            '信息网络传播视听节目许可证:', '广播电视节目制作经营许可证:',
                            '中央网信办违法和不良信息举报中心',
                            '违法和不良信息举报电话:', '举报邮箱:',
                            '隐私协议', '汽车之家 www.autohome.com.cn',
                            '共创团队' 
                        ]

                        # 先清理导航文本
                        # 进一步清理内容，移除导航相关的行
                        # 直接在原始内容中查找尾部关键词的位置
                        footer_start = len(content)  # 默认尾部从内容末尾开始

                        # 查找明确的尾部标识的位置
                        for keyword in footer_keywords:
                            pos = content.find(keyword)
                            if pos != -1 and pos < footer_start:
                                footer_start = pos

                        # 如果找到了尾部标识，截断内容
                        if footer_start < len(content):
                            content = content[:footer_start].strip()

                        # 使用多种分隔符分割内容
                        # 尝试用换行符分割，如果没有换行符，则用空格分割
                        if '\n' in content:
                            lines = content.split('\n')
                        else:
                            # 用多个空格或制表符分割
                            lines = re.split(r'[\s\t]{2,}', content)
                            # 如果分割后仍然只有一行，尝试用单个空格分割
                            if len(lines) == 1 and len(content) > 500:
                                lines = content.split(' ')

                        filtered_lines = []
                        # 查找正文结束的位置（遇到第一个底部关键词就停止）
                        for line in lines:
                            line_stripped = line.strip()
                            # 检查是否包含底部推荐内容的关键词（使用更宽松的匹配）
                            if any(keyword in line_stripped for keyword in footer_keywords):
                                break
                            # 跳过包含导航关键词的行
                            if not any(keyword in line_stripped for keyword in nav_keywords):
                                filtered_lines.append(line)


                        filtered_lines = final_lines

                        content = '\n'.join(filtered_lines).strip()
                        # 如果内容太短，说明过滤掉了太多，可能不是有效内容
                        if len(content) > 50:
                            # 找到有效内容，跳出selector循环
                            break
                        else:
                            content = None
                    else:
                        content = None
        elif is_gasgoo:
            # gasgoo网站的内容在#ArticleContent或.contentDetailed中
            content_elem = soup.select_one('#ArticleContent') or soup.select_one('.contentDetailed')
            if content_elem:
                # 移除脚本和样式标签
                for script in content_elem(["script", "style"]):
                    script.extract()
                content = content_elem.get_text(separator='\n').strip()
                # 检查内容是否有效（排除只有"盖世汽车产业大数据"的情况）
                if content and len(content) < 50 and "盖世汽车产业大数据" in content:
                    content = None
        else:
            # 其他网站的内容提取逻辑
            content_selectors = [
                '.article-content', '.content', '.article-body', 
                '.news-content', '.post-content', '#content',
                '#article-content', 'article', '.main-content'
            ]
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 移除脚本和样式标签
                    for script in content_elem(["script", "style"]):
                        script.extract()
                    content = content_elem.get_text(separator='\n').strip()
                    if content:
                        break

        # 如果没有找到内容，尝试获取整个body的文本
        if not content:
            body = soup.find('body')
            if body:
                for script in body(["script", "style"]):
                    script.extract()
                content = body.get_text(separator='\n').strip()

                # 使用footer_keywords过滤掉新闻后缀
                if content:
                    # 定义底部关键词
                    footer_keywords = [
                        '文章标签', '向编辑', '询底价',
                        '作者其他作品',
                        '进入主页', '相关视频', '论坛推荐',
                        '大家都在问', '扫码下载汽车之家App',
                        '京公网安备', '京ICP备', '信息网络传播视听节目许可证',
                        '广播电视节目制作经营许可证', '中央网信办',
                        '违法和不良信息举报中心', '举报电话', '举报邮箱', '隐私协议',
                        '万 播放',
                        'www.autohome.com.cn',
                        '公司名称：北京车之家信息技术有限公司',
                        '©', '京公网安备',
                        '信息网络传播视听节目许可证:', '广播电视节目制作经营许可证:',
                        '中央网信办违法和不良信息举报中心',
                        '违法和不良信息举报电话:', '举报邮箱:',
                        '隐私协议', '汽车之家 www.autohome.com.cn',
                        '共创团队'
                    ]

                    # 只在内容的最后1/3长度范围内查找footer_keywords
                    content_len = len(content)
                    search_start = int(content_len * 2 / 3)  # 从2/3位置开始搜索
                    search_content = content[search_start:]  # 获取最后1/3的内容

                    # 从屁股后面往前扫描，查找footer_keywords
                    footer_start = len(search_content)  # 默认从最后开始
                    for keyword in footer_keywords:
                        pos = search_content.rfind(keyword)  # 从后往前查找
                        if pos != -1 and pos < footer_start:
                            footer_start = pos

                    # 如果找到了尾部标识，截断内容
                    if footer_start < len(search_content):
                        # 计算在原始content中的位置
                        actual_footer_start = search_start + footer_start
                        content = content[:actual_footer_start].strip()

        # 最终验证：确保内容有效
        if content:
            # 移除多余的空白字符
            content = re.sub(r'\s+', ' ', content).strip()
            # 检查内容是否过短或包含无效内容
            if len(content) < 50 or "盖世汽车产业大数据" in content:
                content = None

        return {
            'title': title or "未知标题",
            'time': news_time,
            'url': url,
            'content': content or "无法提取内容"
        }
    except Exception as e:
        return {
            'title': "获取失败",
            'time': "未知时间",
            'url': url,
            'content': f"获取内容时出错: {str(e)}"
        }

def save_news_to_file(news_list, output_file):
    """将新闻内容保存到文件中"""
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, news in enumerate(news_list, 1):
            # 跳过None值的新闻
            if news is None:
                continue
            f.write(f"===== 新闻 {i} =====\n")
            f.write(f"标题: {news.get('title', '未知标题')}\n")
            f.write(f"时间: {news.get('time', '未知时间')}\n")
            f.write(f"链接: {news.get('url', '未知链接')}\n")
            f.write(f"内容:\n{news.get('content', '无内容')}\n")
            f.write("\n" + "="*50 + "\n\n")

def process_link(link, index, total, lock):
    """处理单个链接的函数，用于多线程"""
    with lock:
        print(f"正在处理第 {index}/{total} 个链接: {link}")
    return extract_news_content(link)

def find_webarchive_files(directory):
    """遍历目录，查找所有.webarchive文件"""
    webarchive_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.webarchive'):
                webarchive_files.append(os.path.join(root, file))
    return webarchive_files

def parse_time_filter(time_str):
    """解析时间过滤参数，返回datetime对象"""
    if not time_str:
        return None

    # 尝试解析带时分秒的格式：YYYY-MM-DD HH:MM
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M')
    except ValueError:
        pass

    # 尝试解析只有日期的格式：YYYY-MM-DD
    try:
        return datetime.strptime(time_str, '%Y-%m-%d')
    except ValueError:
        pass

    # 如果都解析失败，返回None
    return None

def is_news_after_time(news_time_str, filter_time):
    """判断新闻时间是否在过滤时间之后"""
    if not filter_time:
        return True  # 没有设置过滤时间，返回True

    if not news_time_str or news_time_str == "未知时间":
        return True  # 时间未知，默认保留

    # 尝试解析新闻时间
    news_time = None
    time_formats = [
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y年%m月%d日',
        '%Y/%m/%d',
        '%Y/%m/%d %H:%M'
    ]

    for fmt in time_formats:
        try:
            news_time = datetime.strptime(news_time_str, fmt)
            break
        except ValueError:
            continue

    if not news_time:
        return True  # 无法解析时间，默认保留

    # 比较时间
    return news_time >= filter_time

def show_help():
    """显示帮助信息"""
    help_text = """
WebGrep - 从webarchive文件中提取新闻内容

使用方法:
  python WebGrep.py <文件1> [文件2] [文件3] ...
  python WebGrep.py --dir <目录>
  python WebGrep.py --after <日期时间>
  python WebGrep.py --help

参数说明:
  <文件1> [文件2] [文件3] ...  指定一个或多个webarchive文件
  --dir <目录>                  指定包含webarchive文件的目录，脚本会自动遍历该目录及其子目录中的所有.webarchive文件
  --after <日期时间>            只抓取指定时间之后的新闻，格式：YYYY-MM-DD HH:MM 或 YYYY-MM-DD
  --help                        显示此帮助信息

示例:
  python WebGrep.py web1.webarchive web2.webarchive web3.webarchive
  python WebGrep.py --dir /path/to/webarchives
  python WebGrep.py --after "2025-01-01 00:00"
  python WebGrep.py --after "2025-01-01"
  python WebGrep.py --help

功能说明:
  - 从webarchive文件中提取新闻文章链接
  - 自动过滤掉非新闻链接（如图片、CSS、JS等资源）
  - 从新闻链接中提取标题、时间和正文内容
  - 支持多线程处理，提高效率
  - 支持按时间过滤新闻，只抓取指定时间之后的新闻
  - 如果新闻时间无法解析，默认保留该新闻
  - 结果保存到work目录下的文本文件中
"""
    print(help_text)

def main():
    # 检查是否显示帮助信息
    if len(sys.argv) >= 2 and sys.argv[1] in ['--help', '-h', '/h', '/?']:
        show_help()
        return

    if len(sys.argv) < 2:
        print("使用方法: python WebGrep.py <文件1> [文件2] [文件3] ...")
        print("       或: python WebGrep.py --dir <目录>")
        print("       或: python WebGrep.py --after <日期时间>")
        print("       或: python WebGrep.py --help")
        print("示例: python WebGrep.py web1.webarchive web2.webarchive web3.webarchive")
        print("      : python WebGrep.py --dir /path/to/webarchives")
        print("      : python WebGrep.py --after '2025-01-01 00:00'")
        print("      : python WebGrep.py --help")
        return

    # 解析命令行参数
    input_files = []
    time_filter = None
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--dir' and i + 1 < len(sys.argv):
            directory = sys.argv[i + 1]
            if not os.path.isdir(directory):
                print(f"错误: 目录 '{directory}' 不存在或不是一个目录")
                return
            input_files = find_webarchive_files(directory)
            if not input_files:
                print(f"在目录 '{directory}' 中未找到任何.webarchive文件")
                return
            print(f"在目录 '{directory}' 中找到 {len(input_files)} 个.webarchive文件")
            i += 2
        elif arg == '--after' and i + 1 < len(sys.argv):
            time_str = sys.argv[i + 1]
            time_filter = parse_time_filter(time_str)
            if not time_filter:
                print(f"错误: 无法解析时间参数 '{time_str}'，请使用格式：YYYY-MM-DD HH:MM 或 YYYY-MM-DD")
                return
            print(f"时间过滤: 只抓取 {time_filter.strftime('%Y-%m-%d %H:%M')} 之后的新闻")
            i += 2
        elif not arg.startswith('--'):
            input_files.append(arg)
            i += 1
        else:
            print(f"错误: 未知参数 '{arg}'")
            return

    # 检查所有文件是否存在
    for input_file in input_files:
        if not os.path.exists(input_file):
            print(f"错误: 文件 '{input_file}' 不存在")
            return

    # 从所有文件中提取链接
    all_links = []
    for input_file in input_files:
        print(f"正在从文件 '{input_file}' 中提取链接...")
        links = extract_links_from_file(input_file)
        print(f"从 '{input_file}' 找到 {len(links)} 个链接")
        all_links.extend(links)

    # 去重
    all_links = list(set(all_links))
    print(f"总共找到 {len(all_links)} 个唯一链接")

    if not all_links:
        print("未找到任何链接")
        return

    # 设置线程数
    max_workers = 10  # 可以根据需要调整

    # 创建线程锁，用于同步打印
    print_lock = threading.Lock()

    # 使用线程池并行处理链接
    news_list = []
    failed_count = 0  # 统计失败的链接数量
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {
            executor.submit(process_link, link, i+1, len(all_links), print_lock): link 
            for i, link in enumerate(all_links)
        }

        # 等待所有任务完成并收集结果
        for future in as_completed(futures):
            link = futures[future]
            try:
                news = future.result()
                # 检查是否获取失败
                if news and news.get('title') == "获取失败":
                    failed_count += 1
                    news_list.append(news)
                elif news:
                    # 检查新闻时间是否符合过滤条件
                    if is_news_after_time(news.get('time'), time_filter):
                        news_list.append(news)
                    else:
                        print(f"跳过新闻（时间早于过滤时间）: {news.get('title', '未知标题')}")
            except Exception as e:
                failed_count += 1
                print(f"处理链接 {link} 时出错: {str(e)}")

    # 保存到文件
    # 创建work目录（如果不存在）
    work_dir = "work"
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    output_file = os.path.join(work_dir, f"news_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    print(f"正在保存结果到 '{output_file}'...")
    save_news_to_file(news_list, output_file)
    print(f"完成! 已保存 {len(news_list)} 条新闻到 '{output_file}'")

    # 显示失败警告
    if failed_count > 0:
        print(f"\n警告: 共有 {failed_count} 个新闻抓取失败，可能是网络问题或链接无效")

if __name__ == "__main__":
    main()
