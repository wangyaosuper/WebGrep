
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

        # 获取主URL
        if 'WebMainResource' in plist:
            if 'WebResourceURL' in plist['WebMainResource']:
                links.append(plist['WebMainResource']['WebResourceURL'])

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

                    # 使用BeautifulSoup解析HTML并提取所有链接
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

        # 尝试提取标题
        title = None
        if is_gasgoo:
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
        if is_gasgoo:
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
        if is_gasgoo:
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
            f.write(f"===== 新闻 {i} =====\n")
            f.write(f"标题: {news['title']}\n")
            f.write(f"时间: {news['time']}\n")
            f.write(f"链接: {news['url']}\n")
            f.write(f"内容:\n{news['content']}\n")
            f.write("\n" + "="*50 + "\n\n")

def process_link(link, index, total, lock):
    """处理单个链接的函数，用于多线程"""
    with lock:
        print(f"正在处理第 {index}/{total} 个链接: {link}")
    return extract_news_content(link)

def main():
    if len(sys.argv) < 2:
        print("使用方法: python WebGrep.py <文件1> [文件2] [文件3] ...")
        print("示例: python WebGrep.py web1.webarchive web2.webarchive web3.webarchive")
        return

    input_files = sys.argv[1:]

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
                news_list.append(news)
            except Exception as e:
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

if __name__ == "__main__":
    main()
