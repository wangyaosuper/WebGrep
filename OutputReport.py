#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutputReport.py - 新闻抓取输出文件分析报告工具

分析 news_output_*.txt 格式的新闻抓取文件，生成统计报告：
  - 各网站抓取新闻数量
  - 各网站错误统计（未知标题、获取失败标题、未知时间、无法提取内容、获取内容出错）
  - 错误新闻编号明细

用法:
  python OutputReport.py <新闻输出文件路径>
  python OutputReport.py --help
"""

import argparse
import re
import sys
from collections import defaultdict
from urllib.parse import urlparse


def parse_news_file(filepath):
    """
    解析新闻输出文件，返回新闻列表。
    每条新闻为一个字典，包含: id, title, time, link, content
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 无法读取文件 - {e}")
        sys.exit(1)

    # 按 "===== 新闻 N =====" 分割
    news_blocks = re.split(r"===== 新闻 \d+ =====", text)

    news_list = []
    for block in news_blocks:
        block = block.strip()
        if not block:
            continue

        news = {}

        # 提取标题
        title_match = re.search(r"标题:\s*(.*)", block)
        news["title"] = title_match.group(1).strip() if title_match else ""

        # 提取时间
        time_match = re.search(r"时间:\s*(.*)", block)
        news["time"] = time_match.group(1).strip() if time_match else ""

        # 提取链接
        link_match = re.search(r"链接:\s*(.*)", block)
        news["link"] = link_match.group(1).strip() if link_match else ""

        # 提取内容（链接之后到分隔线之间的部分）
        content_match = re.search(r"链接:.*\n内容:\s*\n([\s\S]*?)(?:\n={50,}|$)", block)
        news["content"] = content_match.group(1).strip() if content_match else ""

        news_list.append(news)

    # 重新编号（以文件中的编号为准）
    # 从文件中提取编号
    id_matches = re.findall(r"===== 新闻 (\d+) =====", text)
    if len(id_matches) == len(news_list):
        for i, news in enumerate(news_list):
            news["id"] = int(id_matches[i])
    else:
        for i, news in enumerate(news_list):
            news["id"] = i + 1

    return news_list


# 已知的新闻网站主域名及其显示名称
KNOWN_NEWS_SITES = {
    "ithome.com": "IT之家",
    "autohome.com.cn": "汽车之家",
    "gasgoo.com": "盖世汽车",
    "electrek.co": "Electrek",
    "autonews.com": "AutoNews",
    "autor.com.cn": "汽车商报",
    "9to5mac.com": "9to5Mac",
    "9to5google.com": "9to5Google",
    "dronedj.com": "DroneDJ",
    "spaceexplored.com": "SpaceExplored",
    "solarthermalmagazine.com": "SolarThermalMag",
}


def extract_domain(link):
    """从链接中提取域名，用于识别网站来源。"""
    if not link:
        return "未知来源"
    try:
        parsed = urlparse(link)
        domain = parsed.netloc
        if not domain:
            return "未知来源"
        # 去除 www. 前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return "未知来源"


def get_site_display_name(domain):
    """将域名转换为更友好的显示名称，支持子域名归并到主站。"""
    # 先精确匹配
    if domain in KNOWN_NEWS_SITES:
        return KNOWN_NEWS_SITES[domain]

    # 尝试子域名归并：将 xxx.maindomain.com 归入 maindomain.com
    for main_domain, display_name in KNOWN_NEWS_SITES.items():
        if domain.endswith("." + main_domain):
            return display_name

    # 不在已知新闻网站列表中的域名，归入"其他(非新闻网站)"
    return None


def classify_site(domain):
    """
    对域名进行分类，返回 (display_name, is_news_site)。
    is_news_site 为 True 表示是已知新闻网站，False 表示非新闻网站。
    """
    display_name = get_site_display_name(domain)
    if display_name is not None:
        return display_name, True
    else:
        return domain, False


def analyze_news(news_list):
    """
    分析新闻列表，返回统计结果。
    """
    # 按网站分组统计
    site_news_count = defaultdict(int)       # 各网站新闻总数
    site_error_unknown_title = defaultdict(list)   # 未知标题
    site_error_failed_title = defaultdict(list)    # 获取失败标题
    site_error_unknown_time = defaultdict(list)    # 未知时间
    site_error_no_content = defaultdict(list)      # 无法提取内容
    site_error_fetch_content = defaultdict(list)   # 获取内容出错
    other_domains = defaultdict(int)               # 非新闻网站的域名统计

    OTHER_SITE_LABEL = "其他(非新闻网站)"

    for news in news_list:
        domain = extract_domain(news["link"])
        site_name, is_news_site = classify_site(domain)

        if not is_news_site:
            # 记录非新闻网站的原始域名
            other_domains[domain] += 1
            site_name = OTHER_SITE_LABEL

        site_news_count[site_name] += 1

        # 检查标题错误
        if news["title"] == "未知标题":
            site_error_unknown_title[site_name].append(news["id"])
        elif news["title"] == "获取失败":
            site_error_failed_title[site_name].append(news["id"])

        # 检查时间错误
        if news["time"] == "未知时间":
            site_error_unknown_time[site_name].append(news["id"])

        # 检查内容错误
        if news["content"] == "无法提取内容":
            site_error_no_content[site_name].append(news["id"])
        elif news["content"].startswith("获取内容时出错"):
            site_error_fetch_content[site_name].append(news["id"])

    return {
        "site_news_count": site_news_count,
        "site_error_unknown_title": site_error_unknown_title,
        "site_error_failed_title": site_error_failed_title,
        "site_error_unknown_time": site_error_unknown_time,
        "site_error_no_content": site_error_no_content,
        "site_error_fetch_content": site_error_fetch_content,
        "other_domains": other_domains,
    }


def generate_report(filepath, analysis):
    """生成并打印分析报告。"""
    site_news_count = analysis["site_news_count"]
    site_error_unknown_title = analysis["site_error_unknown_title"]
    site_error_failed_title = analysis["site_error_failed_title"]
    site_error_unknown_time = analysis["site_error_unknown_time"]
    site_error_no_content = analysis["site_error_no_content"]
    site_error_fetch_content = analysis["site_error_fetch_content"]

    other_domains = analysis.get("other_domains", {})

    total_news = sum(site_news_count.values())
    total_errors = (
        sum(len(v) for v in site_error_unknown_title.values())
        + sum(len(v) for v in site_error_failed_title.values())
        + sum(len(v) for v in site_error_unknown_time.values())
        + sum(len(v) for v in site_error_no_content.values())
        + sum(len(v) for v in site_error_fetch_content.values())
    )

    # 收集所有出现错误的网站
    error_sites = set()
    error_sites.update(site_error_unknown_title.keys())
    error_sites.update(site_error_failed_title.keys())
    error_sites.update(site_error_unknown_time.keys())
    error_sites.update(site_error_no_content.keys())
    error_sites.update(site_error_fetch_content.keys())

    separator = "=" * 70
    thin_sep = "-" * 70

    print()
    print(separator)
    print("  新闻抓取输出报告")
    print(separator)
    print(f"  文件: {filepath}")
    print(f"  新闻总数: {total_news}")
    print(f"  涉及网站: {len(site_news_count)} 个")
    print(f"  错误总数: {total_errors} 项")
    print(separator)

    # ===== 第一部分：各网站新闻抓取数量 =====
    print()
    print("【各网站新闻抓取数量】")
    print(thin_sep)
    print(f"  {'网站':<20s} {'新闻数量':>8s}   {'占比':>6s}")
    print(thin_sep)
    for site in sorted(site_news_count.keys()):
        count = site_news_count[site]
        pct = f"{count / total_news * 100:.1f}%" if total_news > 0 else "0.0%"
        print(f"  {site:<20s} {count:>8d}   {pct:>6s}")
    print(thin_sep)
    print(f"  {'合计':<20s} {total_news:>8d}   {'100.0%':>6s}")

    # 显示非新闻网站的域名明细
    OTHER_SITE_LABEL = "其他(非新闻网站)"
    if other_domains:
        print()
        print(f"  \"{OTHER_SITE_LABEL}\"包含的域名:")
        for dom in sorted(other_domains.keys(), key=lambda x: other_domains[x], reverse=True):
            print(f"    - {dom} ({other_domains[dom]} 条)")

    # ===== 第二部分：各网站错误统计 =====
    if error_sites:
        print()
        print("【各网站错误统计】")
        print(thin_sep)

        # 汇总每个网站的各类错误数量
        for site in sorted(error_sites):
            errors = []
            if site in site_error_unknown_title and site_error_unknown_title[site]:
                errors.append(("未知标题", site_error_unknown_title[site]))
            if site in site_error_failed_title and site_error_failed_title[site]:
                errors.append(("获取失败(标题)", site_error_failed_title[site]))
            if site in site_error_unknown_time and site_error_unknown_time[site]:
                errors.append(("未知时间", site_error_unknown_time[site]))
            if site in site_error_no_content and site_error_no_content[site]:
                errors.append(("无法提取内容", site_error_no_content[site]))
            if site in site_error_fetch_content and site_error_fetch_content[site]:
                errors.append(("获取内容出错", site_error_fetch_content[site]))

            if not errors:
                continue

            total_site_errors = sum(len(ids) for _, ids in errors)
            # 计算去重后的错误新闻数量（一条新闻可能有多个错误）
            error_news_ids = set()
            for _, ids in errors:
                error_news_ids.update(ids)
            print(f"  {site} ({total_site_errors} 项错误，{len(error_news_ids)}条新闻错误)")
            for error_type, ids in errors:
                ids_str = ", ".join(str(i) for i in ids)
                print(f"    - {error_type}: {len(ids)} 条  [新闻编号: {ids_str}]")
            print()

        # 错误汇总表
        print("【错误类型汇总】")
        print(thin_sep)
        all_error_types = [
            ("未知标题", site_error_unknown_title),
            ("获取失败(标题)", site_error_failed_title),
            ("未知时间", site_error_unknown_time),
            ("无法提取内容", site_error_no_content),
            ("获取内容出错", site_error_fetch_content),
        ]
        print(f"  {'错误类型':<20s} {'数量':>8s}")
        print(thin_sep)
        for error_name, error_dict in all_error_types:
            count = sum(len(v) for v in error_dict.values())
            print(f"  {error_name:<20s} {count:>8d}")
        print(thin_sep)
        print(f"  {'合计':<20s} {total_errors:>8d}")
    else:
        print()
        print("【错误统计】无错误 ✓")

    print()
    print(separator)
    print("  报告结束")
    print(separator)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="新闻抓取输出文件分析报告工具 - 分析 news_output_*.txt 文件中各网站的抓取情况和错误统计",
        epilog="示例: python OutputReport.py work/news_output_20260516_042151.txt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="要分析的新闻输出文件路径（如 news_output_20260516_042151.txt）",
    )

    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(0)

    news_list = parse_news_file(args.file)

    if not news_list:
        print("文件中未找到任何新闻条目。")
        sys.exit(0)

    analysis = analyze_news(news_list)
    generate_report(args.file, analysis)


if __name__ == "__main__":
    main()
