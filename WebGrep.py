
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

def extract_links_from_file(filename, time_filter=None):
    """从文件中提取所有URL链接"""
    # 检查文件扩展名
    if filename.endswith('.webarchive'):
        # 处理webarchive文件
        return extract_links_from_webarchive(filename, time_filter)
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



def extract_news_from_electrek_list(html_content, time_filter=None):
    """从electrek.co新闻列表页提取新闻信息"""
    soup = BeautifulSoup(html_content, 'html.parser')
    news_list = []

    # 使用集合来去重
    seen_urls = set()

    # 定义需要排除的标题关键词
    excluded_title_keywords = [
        'Subscribe', 'Log in', 'Sign up', 'Menu', 'Search',
        'About', 'Contact', 'Advertise', 'Privacy', 'Terms',
        'Newsletter', 'Follow us', 'Most Popular', 'Guides',
        'Download', 'Podcast'
    ]

    # 查找所有article标签
    articles = soup.find_all('article')
    print(f"找到 {len(articles)} 个article元素")

    for index, article in enumerate(articles, 1):
        try:
            # 查找标题链接
            link_tag = article.find('a', class_='article__title-link')
            if not link_tag:
                continue

            url = link_tag['href']
            # 清理URL中可能的引号
            url = url.strip('"').strip("'")

            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('http'):
                if url.startswith('/'):
                    url = 'https://electrek.co' + url
                else:
                    continue

            # 去重
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 提取标题
            title = link_tag.get_text().strip()

            # 检查标题是否包含排除的关键词
            if any(keyword.lower() in title.lower() for keyword in excluded_title_keywords):
                continue

            # 检查标题长度
            if len(title) < 10:
                continue

            # 查找时间（electrek使用相对时间如"8 hours ago"）
            news_time = "未知时间"
            time_elem = article.find('span', class_='meta__post-date')
            if time_elem:
                news_time = time_elem.get_text().strip()

            # 尝试从URL中提取日期（格式：/2026/05/15/）
            if news_time == "未知时间" or 'ago' in news_time.lower():
                date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
                if date_match:
                    news_time = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

            # 查找摘要（electrek列表页通常没有摘要，但尝试查找）
            summary = ""
            excerpt_elem = article.find('p', class_='article__excerpt')
            if excerpt_elem:
                summary = excerpt_elem.get_text().strip()

            print(f"[{index}/{len(articles)}] 标题: {title}")
            print(f"[{index}/{len(articles)}] 时间: {news_time}")

            # 获取新闻完整内容
            full_content = ""
            try:
                news_data = extract_news_content(url)
                if news_data and news_data.get('content'):
                    full_content = news_data['content']
                    if news_data.get('time') and news_data.get('time') != "未知时间":
                        news_time = news_data['time']
                    if news_data.get('title') and news_data.get('title') != "未知标题":
                        title = news_data['title']
            except Exception as e:
                print(f"获取新闻内容时出错: {str(e)}")
                full_content = "无法获取完整内容"

            # 组合摘要和完整内容
            content = ""
            if summary:
                content = summary
            if full_content and full_content != "无法获取完整内容":
                if content:
                    content = content + "\n" + full_content
                else:
                    content = full_content

            news_list.append({
                'title': title or "未知标题",
                'time': news_time,
                'url': url,
                'content': content or "无摘要"
            })
        except Exception as e:
            continue

    return news_list


def extract_news_from_autonews_list(html_content, time_filter=None):
    """从autonews.com新闻列表页提取新闻信息"""
    soup = BeautifulSoup(html_content, 'html.parser')
    news_list = []

    # 使用集合来去重
    seen_urls = set()

    # 定义需要排除的标题关键词
    excluded_title_keywords = [
        'Subscribe', 'Log in', 'Sign up', 'Menu', 'Search',
        'Topics', 'Industries', 'Companies', 'Opinion', 'Data',
        'Subscribe to Automotive News', 'Newsletter', 'Follow us',
        'Most Read', 'Most Emailed',
        'Top 150 Dealership Groups',

        'Download', 'PDF', 'Excel'
    ]

    # 方法1：从所有包含/news/的链接中提取新闻
    all_links = soup.find_all('a', href=True)
    # 查找所有包含"story" class的链接
    news_links = [a for a in all_links if 'story' in ' '.join(a.get('class', []))]
    print(f"找到 {len(news_links)} 个story链接")
    
    for index, link_tag in enumerate(news_links, 1):
        try:
            print(f"[{index}/{len(news_links)}]")
            url = link_tag['href']

            # 构建完整URL
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('http'):
                url = 'https://www.autonews.com' + url

            # 去重
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 提取标题
            title = link_tag.get_text().strip()

            # 检查标题是否包含排除的关键词
            if any(keyword.lower() in title.lower() for keyword in excluded_title_keywords):
                continue

            # 检查标题长度
            if len(title) < 10:
                continue

            # 查找摘要（在父元素中查找）
            summary = ""
            parent = link_tag.parent
            if parent:
                # 首先尝试从父元素中直接查找包含摘要的p标签
                p_tags = parent.find_all('p')
                for p_tag in p_tags:
                    text = p_tag.get_text().strip()
                    # 确保摘要有足够长度且不是导航文本
                    if text and len(text) > 20 and not any(kw in text.lower() for kw in ['subscribe', 'log in', 'sign up', 'menu', 'search', 'topics', 'industries', 'companies', 'opinion', 'data', 'trending', 'latest', 'most read', 'most emailed']):
                        summary = text
                        break

                # 如果没找到摘要，尝试从兄弟元素中查找
                if not summary:
                    siblings = parent.find_next_siblings()
                    for sibling in siblings:
                        p_tags = sibling.find_all('p')
                        for p_tag in p_tags:
                            text = p_tag.get_text().strip()
                            if text and len(text) > 20 and not any(kw in text.lower() for kw in ['subscribe', 'log in', 'sign up', 'menu', 'search', 'topics', 'industries', 'companies', 'opinion', 'data', 'trending', 'latest', 'most read', 'most emailed']):
                                summary = text
                                break
                        if summary:
                            break

                # 如果还是没找到摘要，尝试从父元素的父元素中查找
                if not summary:
                    grandparent = parent.parent
                    if grandparent:
                        # 查找所有p标签
                        all_p_tags = grandparent.find_all('p')
                        for p_tag in all_p_tags:
                            text = p_tag.get_text().strip()
                            # 确保摘要有足够长度且不是导航文本
                            if text and len(text) > 20 and not any(kw in text.lower() for kw in ['subscribe', 'log in', 'sign up', 'menu', 'search', 'topics', 'industries', 'companies', 'opinion', 'data', 'trending', 'latest', 'most read', 'most emailed']):
                                summary = text
                                break

            # 查找时间
            news_time = "未知时间"
            if parent:
                time_elem = parent.find('time')
                if time_elem:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        try:
                            dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            news_time = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass
                    if news_time == "未知时间":
                        news_time = time_elem.get_text().strip()
                else:
                    # 尝试从兄弟元素中查找时间
                    for sibling in parent.find_next_siblings():
                        time_elem = sibling.find('time')
                        if time_elem:
                            datetime_attr = time_elem.get('datetime')
                            if datetime_attr:
                                try:
                                    dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                                    news_time = dt.strftime('%Y-%m-%d %H:%M')
                                except:
                                    pass
                            if news_time == "未知时间":
                                news_time = time_elem.get_text().strip()
                            break

                    # 如果还没找到，尝试从class包含time或date的元素中提取
                    if news_time == "未知时间":
                        for elem in parent.find_all(class_=re.compile(r'time|date', re.I)):
                            text = elem.get_text().strip()
                            if text and re.search(r'\d{4}', text):
                                news_time = text
                                break

            # 打印当前分析的story链接信息
            print(f"[{index}/{len(news_links)}] 标题: {title}")
            print(f"[{index}/{len(news_links)}] 时间: {news_time}")

            # 检查新闻时间是否符合过滤条件
            #if not is_news_after_time(news_time, time_filter):
            #    print(f"[{index}/{len(news_links)}] 跳过（时间早于过滤时间）")
            #    continue
            #print(f"[{index}/{len(news_links)}] （时间符合条件）")
            # 获取新闻完整内容
            full_content = ""
            try:
                # 使用extract_news_content函数获取完整内容
                news_data = extract_news_content(url)
                if news_data and news_data.get('content'):
                    full_content = news_data['content']
                    # 如果extract_news_content没有提取到时间，使用从列表页提取的时间
                    if news_data.get('time') and news_data.get('time') != "未知时间":
                        news_time = news_data['time']
                    # 如果extract_news_content没有提取到标题，使用从列表页提取的标题
                    if news_data.get('title') and news_data.get('title') != "未知标题":
                        title = news_data['title']
            except Exception as e:
                print(f"获取新闻内容时出错: {str(e)}")
                full_content = "无法获取完整内容"

            # 组合列表页摘要和完整文章内容
            content = ""
            # 只有当摘要与标题不同且长度足够时，才使用列表页的摘要
            if summary:
                content = summary
            if full_content and full_content != "无法获取完整内容":
                if content:
                    content = content + full_content
                else:
                    content = full_content

            news_list.append({
                'title': title or "未知标题",
                'time': news_time,
                'url': url,
                'content': content or "无摘要"
            })
        except Exception as e:
            continue

    # 方法2：如果方法1没有找到新闻，尝试从h2、h3标签中提取
    if not news_list:
        print("抓取Auto News网站新闻，方法1没有找到新闻，尝试方法2...")
        for heading_tag in soup.find_all(['h2', 'h3']):
            try:
                # 先尝试在h2/h3标签内查找a标签
                link_tag = heading_tag.find('a', href=True)

                # 如果h2/h3标签内没有a标签，尝试在父元素中查找
                if not link_tag:
                    parent = heading_tag.parent
                    if parent:
                        link_tag = parent.find('a', href=True)

                # 如果父元素中也没有，尝试在兄弟元素中查找
                if not link_tag:
                    siblings = heading_tag.find_next_siblings()
                    for sibling in siblings:
                        link_tag = sibling.find('a', href=True)
                        if link_tag:
                            break

                if not link_tag:
                    continue

                url = link_tag['href']
                if url.startswith('//'):
                    url = 'https:' + url
                elif not url.startswith('http'):
                    continue

                # 检查URL是否符合autonews.com新闻链接的模式
                if '/news/' not in url:
                    continue

                # 排除列表页本身
                if url.endswith('/news/') or url.endswith('/news'):
                    continue

                # 排除包含分页参数的链接
                if re.search(r'[?&]page=', url):
                    continue

                # 只保留看起来像新闻文章的链接
                if not re.search(r'/news/\d+/', url) and not re.search(r'/news/[a-z0-9-]+', url):
                    continue

                # 去重
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # 提取标题
                title = link_tag.get_text().strip()

                # 检查标题是否包含排除的关键词
                if any(keyword.lower() in title.lower() for keyword in excluded_title_keywords):
                    continue

                # 检查标题长度，太短的可能是导航或功能按钮
                if len(title) < 10:
                    continue

                # 查找摘要（通常在标题附近）
                summary = ""
                # 尝试从heading的父元素中查找摘要
                parent = heading_tag.parent
                if parent:
                    # 查找包含摘要的p标签
                    p_tags = parent.find_all('p')
                    for p_tag in p_tags:
                        text = p_tag.get_text().strip()
                        if text and len(text) > 20:  # 确保摘要有一定长度
                            summary = text
                            break

                # 查找时间（通常在文章元数据中）
                news_time = "未知时间"
                # 尝试从heading的父元素中查找时间
                if parent:
                    # 查找包含时间的元素
                    time_elem = parent.find('time')
                    if time_elem:
                        # 优先使用datetime属性
                        datetime_attr = time_elem.get('datetime')
                        if datetime_attr:
                            try:
                                dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                                news_time = dt.strftime('%Y-%m-%d %H:%M')
                            except:
                                pass
                        # 如果没有datetime属性，使用文本内容
                        if news_time == "未知时间":
                            news_time = time_elem.get_text().strip()
                    else:
                        # 尝试从class包含time或date的元素中提取
                        for elem in parent.find_all(class_=re.compile(r'time|date', re.I)):
                            text = elem.get_text().strip()
                            if text and re.search(r'\d{4}', text):  # 包含年份
                                news_time = text
                                break

                # 获取新闻完整内容
                full_content = ""
                try:
                    # 使用extract_news_content函数获取完整内容
                    news_data = extract_news_content(url)
                    if news_data and news_data.get('content'):
                        full_content = news_data['content']
                        # 如果extract_news_content没有提取到时间，使用从列表页提取的时间
                        if news_data.get('time') and news_data.get('time') != "未知时间":
                            news_time = news_data['time']
                        # 如果extract_news_content没有提取到标题，使用从列表页提取的标题
                        if news_data.get('title') and news_data.get('title') != "未知标题":
                            title = news_data['title']
                except Exception as e:
                    print(f"获取新闻内容时出错: {str(e)}")
                    full_content = "无法获取完整内容"

                # 组合列表页摘要和完整文章内容
                content = ""
                if summary:
                    content = summary
                if full_content and full_content != "无法获取完整内容":
                    if content:
                        content = content + full_content
                    else:
                        content = full_content

                news_list.append({
                    'title': title or "未知标题",
                    'time': news_time,
                    'url': url,
                    'content': content or "无摘要"
                })
            except Exception as e:
                continue

    return news_list

def is_news_link(url):
    """判断URL是否是新闻文章链接"""
    url_lower = url.lower()

    # 排除data:协议链接（如data:image/png）
    if url_lower.startswith('data:'):
        return False

    # 排除图片、CSS、JavaScript等资源链接
    excluded_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.webp', '.avif', '.otf', '.mp4', '.mp3', '.wav', '.flac', '.webm', '.ogg', '.pdf', '.zip', '.gz', '.tar', '.rar', '.7z', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
    for ext in excluded_extensions:
        if url_lower.endswith(ext):
            return False

    # 排除静态资源路径
    excluded_paths = ['/static/', '/assets/', '/images/', '/img/', '/css/', '/js/', '/thumbnail/', '/uploads/', '/fonts/', '/font/', '/icons/', '/favicon/', '/media/', '/video/', '/audio/']
    for path in excluded_paths:
        if path in url_lower:
            return False

    # 排除包含特定查询参数的链接
    excluded_params = ['format=jpg', 'format=png', 'format=gif', 'format=svg', 'format=webp', 'format=avif', 'x-bce-process=image', 'fvd=', 'primer=', 'ver=']
    for param in excluded_params:
        if param in url_lower:
            return False

    # 辅助函数：提取域名部分
    def get_domain_part(url_str):
        url_without_protocol = url_str.split('://')[-1] if '://' in url_str else url_str
        first_slash_pos = url_without_protocol.find('/')
        return url_without_protocol[:first_slash_pos] if first_slash_pos != -1 else url_without_protocol

    # 排除明显的资源域名
    excluded_domains = ['img.', 'image.', 'static.', 'assets.', 'cdn.', 'hm.baidu.com', 'fonts.', 'font.']
    for domain in excluded_domains:
        if domain in url_lower:
            domain_part = get_domain_part(url_lower)
            if domain in domain_part:
                return False

    # 排除字体服务域名
    excluded_font_domains = [
        'typekit.net', 'use.typekit.net', 'fonts.googleapis.com', 'fonts.gstatic.com',
        'cdn.jsdelivr.net', 'fast.fonts.net', 'cloud.typography.com'
    ]
    for domain in excluded_font_domains:
        if domain in url_lower:
            domain_part = get_domain_part(url_lower)
            if domain in domain_part:
                return False

    # 排除头像服务域名
    excluded_avatar_domains = [
        'gravatar.com', 'secure.gravatar.com', 'avatar', 'identicon'
    ]
    for domain in excluded_avatar_domains:
        if domain in url_lower:
            domain_part = get_domain_part(url_lower)
            if domain in domain_part:
                return False

    # 排除广告和隐私相关域名
    excluded_ad_domains = [
        'fundingchoicesmessages.google.com', 'pagead2.googlesyndication.com',
        'adservice.google.com', 'googleads.g.doubleclick.net',
        'tpc.googlesyndication.com', 'ad.doubleclick.net',
        'ads.pubmatic.com', 'bid.g.doubleclick.net',
        'cm.g.doubleclick.net', 'googleadservices.com',
        'adnxs.com', 'ads.yahoo.com', 'amazon-adsystem.com',
        'aax.amazon-adsystem.com', 'c.amazon-adsystem.com'
    ]
    for domain in excluded_ad_domains:
        if domain in url_lower:
            domain_part = get_domain_part(url_lower)
            if domain in domain_part:
                return False

    # 排除视频播放器和嵌入服务域名
    excluded_embed_domains = [
        'videoplayerhub.com', 'player.vimeo.com', 'youtube.com/embed',
        'youtube-nocookie.com', 'players.brightcove.net',
        'cdn.jwplayer.com', 'content.jwplatform.com'
    ]
    for domain in excluded_embed_domains:
        if domain in url_lower:
            domain_part = get_domain_part(url_lower)
            if domain in domain_part:
                return False

    # 排除分析和跟踪域名
    excluded_tracking_domains = [
        'analytics.', 'tracking.', 'stats.', 'metrics.', 'clarity.ms',
        'twitter.com', 't.co', 'facebook.com', 'linkedin.com',
        'doubleclick.net', 'google-analytics.com', 'googletagmanager.com',
        'adobe.com', 'hotjar.com', 'segment.io', 'mixpanel.com',
        'connect.facebook.net', 'pixel.', 'beacon.', 'sentry.io',
        'newrelic.com', 'nr-data.net'
    ]
    for domain in excluded_tracking_domains:
        if domain in url_lower:
            domain_part = get_domain_part(url_lower)
            if domain in domain_part:
                return False

    # 排除非新闻链接的路径
    excluded_paths_news = ['/tougao/', '/?page=', '/register', '/login', '/search', '/icp.html', '/homepage', '/dd_number/', '/special/', '/special_category/', '/creator/', '/new-tech/C-', '/mikecrm.com/', '/avatar/', '/gallery.js', '/embed/']
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

    # 排除URL路径过短的链接（如只有域名+单层路径，通常是导航页）
    parsed_path = url_lower.split('://')[-1] if '://' in url_lower else url_lower
    slash_count = parsed_path.count('/')
    if slash_count < 2:
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

    # 针对autonews.com网站的特殊处理
    if 'autonews.com' in url_lower:
        # autonews.com的新闻链接有多种模式：
        # 1. /news/ 或 /news/数字/文章标题
        # 2. /events/congress/文章标题
        # 3. /品牌/an-文章标题
        # 4. /分类/an-文章标题
        # 例如：/news/ 或 /news/12345/article-title
        # 例如：/events/congress/ane-congress-2026-severinson-volvo-0505/
        # 例如：/mercedes-benz/an-2027-mercedes-glc-ev-reviews-0505/

        # 检查是否包含常见的新闻路径模式
        news_paths = ['/news/', '/events/', '/retail/', '/manufacturing/', '/toyota/', '/mercedes-benz/', 
                   '/honda/', '/stellantis/', '/volvo/', '/general-motors/', '/ford/', '/hyundai/']
        for path in news_paths:
            if path in url_lower:
                # 排除列表页本身
                if url_lower.endswith(path) or url_lower.endswith(path.rstrip('/') + '/'):
                    return False
                # 排除包含分页参数的链接
                if re.search(r'[?&]page=', url_lower):
                    return False
                # 排除包含查询参数的链接（除了可能的跟踪参数）
                if '?' in url_lower and not re.search(r'[?&](ref|share|fbclid|utm_source)=', url_lower):
                    return False
                # 排除下载链接
                if '/download' in url_lower or '/pdf' in url_lower or '/excel' in url_lower:
                    return False
                # 排除报告页面
                if '/top-150' in url_lower or '/data-center' in url_lower:
                    return False
                # 检查是否包含文章标识（如an-或ane-）
                if re.search(r'/an[a-z]*-\d{4}', url_lower):
                    return True
                # 检查是否包含日期模式（如-0505）
                if re.search(r'-\d{4}/$', url_lower):
                    return True
                # 检查是否包含congress
                if 'congress' in url_lower:
                    return True
                return True
        return False

    # 针对electrek.co网站的特殊处理
    if 'electrek.co' in url_lower:
        # electrek.co的新闻链接格式：/年/月/日/英文slug/
        # 例如：/2026/05/15/rivian-r2-configurator-live-pricing-options/
        # 也可能带有 #more-xxx 或 ?extended-comments=1#comments 等后缀
        # 先去掉查询参数和锚点再匹配
        url_path = url_lower.split('?')[0].split('#')[0]
        if re.search(r'/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/?$', url_path):
            return True
        # 排除guides、pages等非新闻链接
        if any(path in url_lower for path in ['/guides/', '/page/', '/author/', '/about/', '/contact/', '/advertise/', '/privacy/', '/terms/', '/category/', '/tag/']):
            return False
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

# 全局变量，用于在extract_links_from_webarchive和主函数之间传递autonews列表页新闻
_autonews_list_cache = []
# 全局变量，用于在extract_links_from_webarchive和主函数之间传递electrek列表页新闻
_electrek_list_cache = []

def extract_links_from_webarchive(filename, time_filter=None):
    """从webarchive文件中提取所有URL链接"""
    global _autonews_list_cache
    global _electrek_list_cache
    try:
        with open(filename, 'rb') as f:
            plist = plistlib.load(f)

        links = []
        is_autohome_list = False
        is_autonews_list = False
        is_electrek_list = False

        # 获取主URL
        if 'WebMainResource' in plist:
            if 'WebResourceURL' in plist['WebMainResource']:
                main_url = plist['WebMainResource']['WebResourceURL']
                links.append(main_url)

                # 检查是否是autohome新闻列表页
                if 'autohome.com.cn/news/' in main_url:
                    is_autohome_list = True

                # 检查是否是autonews.com新闻列表页
                if 'autonews.com' in main_url and ('/news/' in main_url or main_url.endswith('autonews.com/') or main_url.endswith('autonews.com')):
                    is_autonews_list = True

                # 检查是否是electrek.co新闻列表页
                if 'electrek.co' in main_url:
                    is_electrek_list = True

        # 注意：WebSubresources 包含的是页面子资源（字体、CSS、JS、图片等），不包含新闻链接
        # 跳过 WebSubresources，避免引入大量非新闻链接
        # if 'WebSubresources' in plist:
        #     for resource in plist['WebSubresources']:
        #         if 'WebResourceURL' in resource:
        #             links.append(resource['WebResourceURL'])

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
                    # 如果是autonews.com新闻列表页，直接提取新闻信息
                    elif is_autonews_list:
                        print("检测到autonews.com新闻列表页，直接提取新闻信息...")
                        news_list = extract_news_from_autonews_list(html_content, time_filter)
                        if news_list:
                            # 将新闻信息存入全局缓存，避免生成临时文件
                            _autonews_list_cache.extend(news_list)
                            print(f"已从autonews.com新闻列表页提取 {len(news_list)} 条新闻并缓存到内存")
                        else:
                            print("警告：未能从autonews.com新闻列表页提取到新闻，可能是因为新闻内容是通过JavaScript动态加载的")
                        # 同时也提取链接，保持原有功能
                        soup = BeautifulSoup(html_content, 'html.parser')
                        for a_tag in soup.find_all('a', href=True):
                            href = a_tag['href']
                            # 只处理autonews.com的链接
                            if 'autonews.com' in href or href.startswith('/'):
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
                    # 如果是electrek.co新闻列表页，直接提取新闻信息
                    elif is_electrek_list:
                        print("检测到electrek.co新闻列表页，直接提取新闻信息...")
                        news_list = extract_news_from_electrek_list(html_content, time_filter)
                        if news_list:
                            # 将新闻信息存入全局缓存，避免生成临时文件
                            _electrek_list_cache.extend(news_list)
                            print(f"已从electrek.co新闻列表页提取 {len(news_list)} 条新闻并缓存到内存")
                        else:
                            print("警告：未能从electrek.co新闻列表页提取到新闻")
                        # electrek列表页已经通过extract_news_from_electrek_list获取了完整新闻内容
                        # 不再提取链接，避免与缓存新闻重复（同一文章的#more-xxx和?comments变体会导致重复）
                        print("electrek.co列表页新闻已缓存，跳过链接提取以避免重复")
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

        # 检查是否是ithome网站
        is_ithome = 'ithome.com' in url.lower()

        # 检查是否是autonews.com网站
        is_autonews = 'autonews.com' in url.lower()

        # 检查是否是electrek.co网站
        is_electrek = 'electrek.co' in url.lower()

        # 尝试提取标题
        title = None
        if is_autonews:
            # autonews.com网站的标题提取逻辑
            # 首先尝试从meta标签中提取标题
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                title = meta_title['content'].strip()

            # 如果没有从meta标签获取到标题，尝试从h1标签提取
            if not title:
                h1_tags = soup.find_all('h1')
                if h1_tags:
                    for h1_tag in h1_tags:
                        title_text = h1_tag.get_text().strip()
                        # 过滤掉明显不是新闻标题的元素
                        excluded_keywords = [
                            'Subscribe', 'Log in', 'Sign up', 'Menu', 'Search',
                            'Topics', 'Industries', 'Companies', 'Opinion', 'Data',
                            'Subscribe to Automotive News', 'Newsletter', 'Follow us',
                            'Trending', 'Latest', 'Most Read', 'Most Emailed',
                            'Home', 'News', 'Features', 'Opinion', 'Data',
                            'Industries', 'Companies', 'Events', 'More', 'Contact'
                        ]
                        # 检查标题是否包含排除的关键词
                        if title_text and len(title_text) > 10 and not any(keyword.lower() in title_text.lower() for keyword in excluded_keywords):
                            title = title_text
                            break

            # 如果没有找到标题，尝试其他选择器
            if not title:
                title_selectors = ['.article-title', '.news-title', '.title', 'h1']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title_text = title_elem.get_text().strip()
                        # 再次检查标题是否包含排除的关键词
                        excluded_keywords = [
                            'Subscribe', 'Log in', 'Sign up', 'Menu', 'Search',
                            'Topics', 'Industries', 'Companies', 'Opinion', 'Data',
                            'Subscribe to Automotive News', 'Newsletter', 'Follow us',
                            'Trending', 'Latest', 'Most Read', 'Most Emailed',
                            'Home', 'News', 'Features', 'Opinion', 'Data',
                            'Industries', 'Companies', 'Events', 'More', 'Contact'
                        ]
                        if title_text and len(title_text) > 5 and not any(keyword.lower() in title_text.lower() for keyword in excluded_keywords):
                            title = title_text
                            break
                        else:
                            title = None

            # 对于autonews.com网站，如果标题为空或未知，则跳过这条新闻
            if not title or title == "未知标题":
                return None
        elif is_electrek:
            # electrek.co网站的标题提取逻辑
            # 首先尝试从meta标签中提取标题
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                title = meta_title['content'].strip()

            # 如果没有从meta标签获取到标题，尝试从h1标签提取
            if not title:
                h1_tags = soup.find_all('h1')
                if h1_tags:
                    for h1_tag in h1_tags:
                        title_text = h1_tag.get_text().strip()
                        excluded_keywords = [
                            'Subscribe', 'Log in', 'Sign up', 'Menu', 'Search',
                            'About', 'Contact', 'Advertise', 'Privacy', 'Terms',
                            'Newsletter', 'Follow us', 'Most Popular', 'Guides',
                            'Home', 'Electric Vehicle', 'EV', 'Solar', 'Battery'
                        ]
                        if title_text and len(title_text) > 10 and not any(keyword.lower() in title_text.lower() for keyword in excluded_keywords):
                            title = title_text
                            break

            # 如果没有找到标题，尝试其他选择器
            if not title:
                title_selectors = ['.article-title', '.news-title', '.title', 'h2']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title_text = title_elem.get_text().strip()
                        if title_text and len(title_text) > 5:
                            title = title_text
                            break

            # 对于electrek.co网站，如果标题为空或未知，则跳过这条新闻
            if not title or title == "未知标题":
                return None
        elif is_autohome:
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
        if is_autonews:
            # autonews.com网站的时间提取逻辑
            # 首先尝试从meta标签中提取时间
            meta_time = soup.find('meta', property='article:published_time')
            if meta_time and meta_time.get('content'):
                time_text = meta_time['content'].strip()
                # 尝试解析ISO格式时间
                try:
                    dt = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                    news_time = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass

            # 如果没有从meta标签获取到时间，尝试从其他meta标签提取
            if news_time == "未知时间":
                meta_time = soup.find('meta', property='og:article:published_time')
                if meta_time and meta_time.get('content'):
                    time_text = meta_time['content'].strip()
                    try:
                        dt = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                        news_time = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass

            # 如果还是没有提取到时间，尝试从time标签中提取
            if news_time == "未知时间":
                time_tag = soup.find('time')
                if time_tag:
                    # 优先使用datetime属性
                    datetime_attr = time_tag.get('datetime')
                    if datetime_attr:
                        try:
                            dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            news_time = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass
                    # 如果没有datetime属性，使用文本内容
                    if news_time == "未知时间":
                        time_text = time_tag.get_text().strip()
                        if time_text and re.search(r'\d{4}', time_text):  # 包含年份
                            news_time = time_text

            # 如果还是没有提取到时间，尝试从特定class的元素中提取
            if news_time == "未知时间":
                # autonews.com可能使用特定的class来显示时间
                time_selectors_autonews = [
                    '.article-date', '.publish-date', '.post-date',
                    '.entry-date', '.story-date', '.byline-date'
                ]
                for selector in time_selectors_autonews:
                    time_elem = soup.select_one(selector)
                    if time_elem:
                        time_text = time_elem.get_text().strip()
                        if time_text and re.search(r'\d{4}', time_text):  # 包含年份
                            news_time = time_text
                            break

            # 如果还是没有提取到时间，尝试从HTML源码中提取
            if news_time == "未知时间":
                # 尝试从HTML源码中提取时间
                html_content = str(soup)
                # 匹配格式：2026-05-04T15:17:29+00:00 或 2026-05-04 15:17:29
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}[T\s]\d{1,2}:\d{1,2}:\d{1,2})', html_content)
                if date_match:
                    time_str = date_match.group(1)
                    # 将时间格式标准化为 YYYY-MM-DD HH:MM
                    try:
                        # 尝试多种时间格式解析
                        time_formats = [
                            '%Y-%m-%dT%H:%M:%S%z',
                            '%Y-%m-%d %H:%M:%S',
                            '%Y-%m-%dT%H:%M:%S',
                            '%Y-%m-%d %H:%M'
                        ]
                        for fmt in time_formats:
                            try:
                                dt = datetime.strptime(time_str, fmt)
                                news_time = dt.strftime('%Y-%m-%d %H:%M')
                                break
                            except:
                                continue
                    except:
                        pass
        elif is_electrek:
            # electrek.co网站的时间提取逻辑
            # 首先尝试从meta标签中提取时间
            meta_time = soup.find('meta', property='article:published_time')
            if meta_time and meta_time.get('content'):
                time_text = meta_time['content'].strip()
                try:
                    dt = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                    news_time = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass

            # 尝试从time标签中提取
            if news_time == "未知时间":
                time_tag = soup.find('time')
                if time_tag:
                    datetime_attr = time_tag.get('datetime')
                    if datetime_attr:
                        try:
                            dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            news_time = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass
                    if news_time == "未知时间":
                        time_text = time_tag.get_text().strip()
                        if time_text and re.search(r'\d{4}', time_text):
                            news_time = time_text

            # 尝试从span.meta__post-date提取
            if news_time == "未知时间":
                date_span = soup.find('span', class_='meta__post-date')
                if date_span:
                    news_time = date_span.get_text().strip()

            # 尝试从URL中提取日期（格式：/2026/05/15/）
            if news_time == "未知时间" or 'ago' in news_time.lower():
                date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
                if date_match:
                    news_time = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

            # 尝试从HTML源码中提取ISO格式时间
            if news_time == "未知时间":
                html_content_str = str(soup)
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}[T\s]\d{1,2}:\d{1,2}:\d{1,2})', html_content_str)
                if date_match:
                    time_str = date_match.group(1)
                    try:
                        time_formats = ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']
                        for fmt in time_formats:
                            try:
                                dt = datetime.strptime(time_str, fmt)
                                news_time = dt.strftime('%Y-%m-%d %H:%M')
                                break
                            except:
                                continue
                    except:
                        pass
        elif is_ithome:
            # ithome网站的时间提取逻辑
            # IT之家的文章内容中包含时间信息，格式如："2026/5/4 15:17:29"
            # 需要从文章内容中提取这个时间
            # 首先尝试从meta标签中提取时间
            meta_time = soup.find('meta', property='article:published_time')
            if meta_time and meta_time.get('content'):
                time_text = meta_time['content'].strip()
                # 尝试解析ISO格式时间
                try:
                    dt = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                    news_time = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass

            # 如果没有从meta标签获取到时间，尝试从文章内容中提取
            if news_time == "未知时间":
                # 尝试从HTML源码中提取时间
                html_content = str(soup)
                # 匹配格式：2026/5/4 15:17:29 或 2026/05/04 15:17:29
                date_match = re.search(r'(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})', html_content)
                if date_match:
                    time_str = date_match.group(1)
                    # 将时间格式标准化为 YYYY-MM-DD HH:MM
                    try:
                        # 尝试多种时间格式解析
                        time_formats = [
                            '%Y/%m/%d %H:%M:%S',
                            '%Y/%m/%d %H:%M',
                            '%Y/%m/%d %H:%M',
                            '%Y/%m/%d %H:%M:%S'
                        ]
                        for fmt in time_formats:
                            try:
                                dt = datetime.strptime(time_str, fmt)
                                news_time = dt.strftime('%Y-%m-%d %H:%M')
                                break
                            except:
                                continue
                    except:
                        pass

            # 如果还是没有提取到时间，尝试从body文本中提取
            if news_time == "未知时间":
                body = soup.find('body')
                if body:
                    body_text = body.get_text()
                    # 匹配格式：2026/5/4 15:17:29 或 2026/05/04 15:17:29
                    date_match = re.search(r'(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})', body_text)
                    if date_match:
                        time_str = date_match.group(1)
                        # 将时间格式标准化为 YYYY-MM-DD HH:MM
                        try:
                            # 尝试多种时间格式解析
                            time_formats = [
                                '%Y/%m/%d %H:%M:%S',
                                '%Y/%m/%d %H:%M',
                                '%Y/%m/%d %H:%M',
                                '%Y/%m/%d %H:%M:%S'
                            ]
                            for fmt in time_formats:
                                try:
                                    dt = datetime.strptime(time_str, fmt)
                                    news_time = dt.strftime('%Y-%m-%d %H:%M')
                                    break
                                except:
                                    continue
                        except:
                            pass

            # 如果还是没有提取到时间，尝试从标题后的文本中提取
            if news_time == "未知时间":
                # 查找标题元素
                title_elem = soup.find('h1')
                if title_elem:
                    # 获取标题后的兄弟元素
                    next_elem = title_elem.find_next_sibling()
                    while next_elem and news_time == "未知时间":
                        elem_text = next_elem.get_text()
                        # 匹配格式：2026/5/4 15:17:29 或 2026/05/04 15:17:29
                        date_match = re.search(r'(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})', elem_text)
                        if date_match:
                            time_str = date_match.group(1)
                            # 将时间格式标准化为 YYYY-MM-DD HH:MM
                            try:
                                # 尝试多种时间格式解析
                                time_formats = [
                                    '%Y/%m/%d %H:%M:%S',
                                    '%Y/%m/%d %H:%M',
                                    '%Y/%m/%d %H:%M',
                                    '%Y/%m/%d %H:%M:%S'
                                ]
                                for fmt in time_formats:
                                    try:
                                        dt = datetime.strptime(time_str, fmt)
                                        news_time = dt.strftime('%Y-%m-%d %H:%M')
                                        break
                                    except:
                                        continue
                            except:
                                pass
                        next_elem = next_elem.find_next_sibling()
        elif is_autor:
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
            # gasgoo网站的时间提取逻辑
            # 首先尝试从userInfo div中查找时间
            user_info = soup.find('div', class_='userInfo')
            if user_info:
                # 查找所有span标签，找到包含日期的那个
                time_spans = user_info.find_all('span')
                for span in time_spans:
                    text = span.get_text().strip()
                    # 验证是否包含日期格式（YYYY-MM-DD或YYYY年MM月DD日）
                    if re.search(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}', text):
                        news_time = text
                        break

            # 如果没有找到时间，尝试从文章元数据中提取
            if news_time == "未知时间":
                # 尝试从meta标签中提取时间
                meta_time = soup.find('meta', property='article:published_time')
                if meta_time and meta_time.get('content'):
                    time_text = meta_time['content'].strip()
                    try:
                        dt = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                        news_time = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass

            # 如果还是没有找到时间，尝试其他选择器
            if news_time == "未知时间":
                time_selectors = ['.time', '.date', '.publish-time', '.article-time', '.news-time', 'time', '.pub-time']
                for selector in time_selectors:
                    time_elem = soup.select_one(selector)
                    if time_elem:
                        time_text = time_elem.get_text().strip()
                        # 验证时间格式（包含年月日）
                        if re.search(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}', time_text):
                            news_time = time_text
                            break

            # 如果还是没有找到时间，尝试从HTML源码中提取
            if news_time == "未知时间":
                html_content = str(soup)
                # 匹配格式：2026-05-08 11:05:46 或 2026年5月8日
                date_match = re.search(r'(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日\s]*\d{1,2}:\d{1,2}:\d{1,2})', html_content)
                if date_match:
                    news_time = date_match.group(1)
        else:
            news_time = time_elem.get_text().strip() if time_elem else "未知时间"

        # 尝试提取正文内容
        content = None
        if is_autonews:
            # autonews.com网站的内容提取逻辑
            # 查找文章内容区域
            content_selectors = [
                '.article-content', '.content', '.article-body',
                '.news-content', '.post-content', '#content',
                '#article-content', 'article', '.main-content',
                '.entry-content', '.story-content'
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
                        '.author-works', '.newsletter', '.subscribe-box',
                        '.trending', '.most-read', '.most-emailed'
                    ]

                    # 移除不需要的元素
                    for remove_selector in remove_selectors:
                        for elem in content_elem.select(remove_selector):
                            elem.extract()

                    content = content_elem.get_text(separator='\n').strip()
                    # 验证内容有效性
                    if content and len(content) > 100:
                        # 如果内容太短，说明过滤掉了太多，可能不是有效内容
                        if len(content) > 50:
                            # 找到有效内容，跳出selector循环
                            break
                        else:
                            content = None
                    else:
                        content = None
        elif is_autohome:
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
        elif is_electrek:
            # electrek.co网站的内容提取逻辑
            content_selectors = [
                '.article-content', '.post-content', '.entry-content',
                'article .content', '.article__body', '.post-body',
                'article', '.main-content'
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
                        '.newsletter', '.subscribe-box', '.trending',
                        '.most-popular', '.social-share', '.post-meta',
                        '.article__meta-guides', '.article__share'
                    ]

                    # 移除不需要的元素
                    for remove_selector in remove_selectors:
                        for elem in content_elem.select(remove_selector):
                            elem.extract()

                    content = content_elem.get_text(separator='\n').strip()
                    # 验证内容有效性
                    if content and len(content) > 100:
                        break
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

            # 获取并过滤内容
            content = news.get('content', '无内容')

            # 只移除"Skip to main content"字符串，保留所有其他内容
            content = content.replace('Skip to main content', '').strip()

            # 改进的过滤逻辑：只在内容的最后1/3部分查找footer关键词
            # 这样可以避免过滤掉出现在内容中间的"Featured Stories"等
            footer_start = len(content)
            footer_keywords = [
                'Featured Stories',
                'Used Cars',
                'Here\'s our 2026 list',
                'Subscribe to Automotive News',
                'Follow us on',
                'Copyright',
                'Privacy Policy',
                'Privacy Request',
                'Terms and Conditions',
                'Return to homepage',
                'Footer',
                'About Us',
                'Advertise',
                'Subscribe to Electrek',
                'FTC: We use income earning auto affiliate links',
                'More from Electrek',
                'Comments',
                'Guides'
            ]

            # 只在内容的最后1/3长度范围内查找footer_keywords
            if len(content) > 100:  # 只有内容足够长时才进行过滤
                search_start = int(len(content) * 1 / 5)  # 从2/3位置开始搜索
                search_content = content[search_start:]  # 获取最后1/3的内容

                # 从后往前查找footer_keywords
                for keyword in footer_keywords:
                    pos = search_content.rfind(keyword)  # 使用rfind从后往前查找
                    if pos != -1:
                        # 计算在原始content中的位置
                        actual_pos = search_start + pos
                        if actual_pos < footer_start:
                            footer_start = actual_pos

            if footer_start < len(content):
                content = content[:footer_start].strip()

            f.write(f"内容:\n{content}\n")
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
        '%Y-%m-%d %H:%M:%S',  # 支持gasgoo网站的时间格式（包含秒）
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
        links = extract_links_from_file(input_file, time_filter)
        print(f"从 '{input_file}' 找到 {len(links)} 个链接")
        all_links.extend(links)

    # 从全局缓存中获取autonews列表页新闻
    autonews_news_from_list = _autonews_list_cache[:]
    if autonews_news_from_list:
        print(f"从内存缓存中获取了 {len(autonews_news_from_list)} 条从autonews列表页提取的新闻")

    # 从全局缓存中获取electrek列表页新闻
    electrek_news_from_list = _electrek_list_cache[:]
    if electrek_news_from_list:
        print(f"从内存缓存中获取了 {len(electrek_news_from_list)} 条从electrek列表页提取的新闻")

    # 去重
    all_links = list(set(all_links))
    print(f"总共找到 {len(all_links)} 个唯一链接")

    # 使用线程池并行处理链接
    news_list = []
    failed_count = 0  # 统计失败的链接数量

    if all_links:
        # 设置线程数
        max_workers = 10  # 可以根据需要调整

        # 创建线程锁，用于同步打印
        print_lock = threading.Lock()

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
                        # 不再将失败的新闻写入输出文件
                        print(f"跳过失败链接: {link}")
                    elif news:
                        # 检查内容是否为"无法提取内容"或"未知标题"
                        if news.get('content') == "无法提取内容" or news.get('title') == "未知标题":
                            failed_count += 1
                            print(f"跳过无效新闻（标题或内容无效）: {link}")
                        # 检查新闻时间是否符合过滤条件
                        elif is_news_after_time(news.get('time'), time_filter):
                            news_list.append(news)
                        else:
                            print(f"跳过新闻（时间早于过滤时间）: {news.get('title', '未知标题')}")
                except Exception as e:
                    failed_count += 1
                    print(f"处理链接 {link} 时出错: {str(e)}")
    else:
        if not autonews_news_from_list and not electrek_news_from_list:
            print("未找到任何链接，也没有缓存新闻")
            return
        print("未找到需要单独抓取的链接，但有缓存新闻，继续处理缓存...")

    # 保存到文件
    # 创建work目录（如果不存在）
    work_dir = "work"
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    # 将从autonews列表页提取的新闻添加到主新闻列表
    if autonews_news_from_list:
        print(f"\n添加 {len(autonews_news_from_list)} 条从autonews列表页提取的新闻到主列表...")
        # 去重：检查URL是否已存在
        existing_urls = {news.get('url') for news in news_list}
        for news in autonews_news_from_list:
            if news.get('url') not in existing_urls:
                # 检查新闻时间是否符合过滤条件
                if is_news_after_time(news.get('time'), time_filter):
                    news_list.append(news)
                    existing_urls.add(news.get('url'))
                else:
                    print(f"跳过autonews新闻（时间早于过滤时间）: {news.get('title', '未知标题')}")
            else:
                print(f"跳过重复的autonews新闻: {news.get('title', '未知标题')}")

    # 将从electrek列表页提取的新闻添加到主新闻列表
    if electrek_news_from_list:
        print(f"\n添加 {len(electrek_news_from_list)} 条从electrek列表页提取的新闻到主列表...")
        # 去重：检查URL是否已存在
        existing_urls = {news.get('url') for news in news_list}
        for news in electrek_news_from_list:
            if news.get('url') not in existing_urls:
                # 检查新闻时间是否符合过滤条件
                if is_news_after_time(news.get('time'), time_filter):
                    news_list.append(news)
                    existing_urls.add(news.get('url'))
                else:
                    print(f"跳过electrek新闻（时间早于过滤时间）: {news.get('title', '未知标题')}")
            else:
                print(f"跳过重复的electrek新闻: {news.get('title', '未知标题')}")

    output_file = os.path.join(work_dir, f"news_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    print(f"正在保存结果到 '{output_file}'...")
    save_news_to_file(news_list, output_file)
    print(f"完成! 已保存 {len(news_list)} 条新闻到 '{output_file}'")

    # 显示失败警告
    if failed_count > 0:
        print(f"\n警告: 共有 {failed_count} 个新闻抓取失败，可能是网络问题或链接无效")

if __name__ == "__main__":
    main()
