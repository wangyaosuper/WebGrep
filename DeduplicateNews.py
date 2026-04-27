#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻去重脚本
用于删除重复的新闻，重复的新闻是指新闻标题和内容都相同的新闻
"""

import re
import argparse
import sys
from pathlib import Path


def parse_news_file(file_path):
    """
    解析新闻文件，返回新闻列表
    每个新闻是一个字典，包含编号、标题、时间、链接、内容
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 使用正则表达式分割新闻
    news_pattern = r'''===== 新闻 (\d+) =====\s*
标题: (.*?)\s*
时间: (.*?)\s*
链接: (.*?)\s*
内容:\s*(.*?)\s*
(?=\n={50,}|\Z)'''
    news_list = []

    for match in re.finditer(news_pattern, content, re.DOTALL):
        news_id = int(match.group(1))
        title = match.group(2).strip()
        time = match.group(3).strip()
        link = match.group(4).strip()
        news_content = match.group(5).strip()

        news_list.append({
            'id': news_id,
            'title': title,
            'time': time,
            'link': link,
            'content': news_content
        })

    return news_list


def find_duplicates(news_list):
    """
    找出重复的新闻
    重复的定义：标题和内容都相同
    返回: (unique_news, duplicates_info)
    """
    seen = {}
    duplicates = []
    unique_news = []

    for news in news_list:
        # 使用标题和内容的组合作为唯一标识
        key = (news['title'], news['content'])

        if key in seen:
            # 发现重复
            original_id = seen[key]
            duplicate_id = news['id']
            duplicates.append({
                'original_id': original_id,
                'duplicate_id': duplicate_id,
                'title': news['title']
            })
            print(f"发现重复: 编号 {original_id} 和 编号 {duplicate_id} 的新闻重复")
            print(f"  标题: {news['title'][:50]}...")
        else:
            seen[key] = news['id']
            unique_news.append(news)

    return unique_news, duplicates


def write_news_file(news_list, output_path):
    """
    将新闻列表写入文件
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for idx, news in enumerate(news_list, 1):
            # 更新编号
            news['id'] = idx
            f.write(f"===== 新闻 {idx} =====\n")
            f.write(f"标题: {news['title']}\n")
            f.write(f"时间: {news['time']}\n")
            f.write(f"链接: {news['link']}\n")
            f.write(f"内容:\n{news['content']}\n\n")
            f.write("=" * 50 + "\n\n")


def main():
    parser = argparse.ArgumentParser(
        description='新闻去重工具 - 删除标题和内容都相同的重复新闻',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例用法:
  python Deduplicate.py input.txt
  python Deduplicate.py work/news_output.txt -o output.txt
        '''
    )

    parser.add_argument(
        'input_file',
        help='输入的新闻文件路径'
    )

    parser.add_argument(
        '-o', '--output',
        help='输出文件路径 (默认为: DEDUPLICATED_原文件名)',
        default=None
    )

    args = parser.parse_args()

    # 检查输入文件是否存在
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"错误: 输入文件 '{args.input_file}' 不存在")
        sys.exit(1)

    # 确定输出文件路径
    if args.output:
        output_path = Path(args.output)
    else:
        # 默认放在work目录下
        work_dir = Path('work')
        # 如果work目录不存在，自动创建
        if not work_dir.exists():
            work_dir.mkdir(parents=True, exist_ok=True)
            print(f"已创建 work 目录")
        output_path = work_dir / f"DEDUPLICATED_{input_path.name}"

    print(f"\n开始处理文件: {input_path}")
    print(f"输出文件: {output_path}\n")

    # 解析新闻文件
    print("正在解析新闻文件...")
    news_list = parse_news_file(input_path)
    print(f"共找到 {len(news_list)} 条新闻\n")

    # 查找重复新闻
    print("正在查找重复新闻...")
    unique_news, duplicates = find_duplicates(news_list)
    print(f"\n发现 {len(duplicates)} 条重复新闻")
    print(f"去重后剩余 {len(unique_news)} 条新闻\n")

    # 输出删除的重复新闻信息
    if duplicates:
        print("\n删除的重复新闻详情:")
        print("-" * 80)
        for dup in duplicates:
            print(f"  删除编号 {dup['duplicate_id']} 的新闻 (与编号 {dup['original_id']} 重复)")
            print(f"    标题: {dup['title'][:80]}...")
            print()

    # 写入去重后的文件
    print(f"正在写入去重后的文件: {output_path}")
    write_news_file(unique_news, output_path)

    print(f"\n处理完成!")
    print(f"  原文件: {input_path} ({len(news_list)} 条新闻)")
    print(f"  新文件: {output_path} ({len(unique_news)} 条新闻)")
    print(f"  删除重复: {len(duplicates)} 条")


if __name__ == '__main__':
    main()
