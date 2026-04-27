
import os
import re
import argparse
from datetime import datetime
from pathlib import Path

def count_news_in_file(file_path):
    """统计文件中的新闻数量"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 匹配新闻编号模式: ===== 新闻 X =====
        news_pattern = r'^===== 新闻 \d+ ====='
        news_list = re.findall(news_pattern, content, re.MULTILINE)
        return len(news_list)
    except Exception as e:
        print(f"统计文件 {file_path} 中的新闻数量时出错: {e}")
        return 0

def extract_news_items(content):
    """从内容中提取新闻条目"""
    # 匹配新闻编号模式: ===== 新闻 X =====
    news_pattern = r'^===== 新闻 \d+ ====='
    # 找到所有匹配的位置
    matches = list(re.finditer(news_pattern, content, re.MULTILINE))

    if not matches:
        return [content]

    news_items = []
    for i, match in enumerate(matches):
        start = match.start()
        # 下一条新闻的起始位置
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        news_items.append(content[start:end])

    return news_items

def renumber_news_items(news_items, start_number=1):
    """重新编号新闻条目"""
    renumbered = []
    for i, item in enumerate(news_items):
        # 替换原有的编号: ===== 新闻 X =====
        new_item = re.sub(r'^===== 新闻 \d+ =====',
                         f"===== 新闻 {i+start_number} =====",
                         item,
                         count=1,
                         flags=re.MULTILINE)
        renumbered.append(new_item)
    return renumbered

def process_file(file_path, file_info_list, current_news_number):
    """处理单个文件，提取新闻并返回格式化内容"""
    file_name = os.path.basename(file_path)

    # 从文件名中提取日期信息
    date_match = re.search(r'(\d{4})(\d{2})(\d{2})', file_name)
    date_str = ""
    if date_match:
        year, month, day = date_match.groups()
        date_str = f"{year}年{month}月{day}日"

    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取新闻条目
    news_items = extract_news_items(content)
    news_count = len(news_items)

    # 记录文件信息
    file_info_list.append({
        'file_name': file_name,
        'date': date_str,
        'news_count': news_count
    })

    # 添加文件来源标记
    header = f"\n{'='*80}\n"
    header += f"【文件来源: {file_name}"
    if date_str:
        header += f" | 日期: {date_str}"
    header += f" | 新闻数量: {news_count}条】\n"
    header += f"{'='*80}\n\n"

    # 重新编号新闻条目，从当前新闻编号开始
    renumbered_items = renumber_news_items(news_items, current_news_number)

    # 组合内容
    formatted_content = header + "\n".join(renumbered_items)

    return formatted_content, news_count

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="合并多个新闻txt文件，重新编号并添加来源标记",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例用法:
  python ConcatTxt.py file1.txt file2.txt  # 合并指定的txt文件
  python ConcatTxt.py work/news_output_20260426_060455.txt work/news_output_20260428_052015.txt  # 合并work目录下的指定文件
  python ConcatTxt.py --help             # 显示帮助信息
        """
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0"
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="要合并的txt文件路径"
    )

    return parser.parse_args()

def main():
    # 解析命令行参数
    args = parse_args()

    # 获取当前目录
    current_dir = os.getcwd()
    print(f"当前工作目录: {current_dir}")

    # 检查用户是否指定了文件
    if not args.files:
        print("错误: 请指定要合并的txt文件！")
        print("使用 --help 查看使用说明")
        return

    # 处理用户指定的文件
    txt_files = []
    for file_path in args.files:
        if os.path.exists(file_path):
            txt_files.append(os.path.abspath(file_path))
        else:
            print(f"警告: 文件不存在 - {file_path}")

    if not txt_files:
        print("错误: 没有找到有效的文件！")
        return

    print(f"\n找到 {len(txt_files)} 个txt文件:")
    for i, file_path in enumerate(txt_files, 1):
        print(f"  {i}. {os.path.basename(file_path)}")

    # 处理每个文件
    file_info_list = []
    all_content = []
    total_news = 0
    current_news_number = 1  # 当前新闻编号

    print("\n开始处理文件...")
    print("-" * 80)

    for i, file_path in enumerate(txt_files, 1):
        print(f"\n处理文件 {i}/{len(txt_files)}: {os.path.basename(file_path)}")

        formatted_content, news_count = process_file(file_path, file_info_list, current_news_number)
        all_content.append(formatted_content)
        total_news += news_count
        current_news_number += news_count  # 更新新闻编号

        print(f"  - 提取新闻数量: {news_count}条")
        print(f"  - 新闻编号范围: {current_news_number - news_count} - {current_news_number - 1}")

    # 生成合并后的文件名，使用英文标识，保存到work目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"CONCAT_news_summary_{timestamp}.txt"

    # 确保work目录存在
    work_dir = os.path.join(current_dir, "work")
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    output_path = os.path.join(work_dir, output_filename)

    # 写入合并后的内容
    with open(output_path, 'w', encoding='utf-8') as f:
        # 添加总体信息
        summary = f"{'='*80}\n"
        summary += f"新闻合并汇总报告\n"
        summary += f"{'='*80}\n"
        summary += f"合并时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        summary += f"合并文件数量: {len(txt_files)}个\n"
        summary += f"总新闻数量: {total_news}条\n"
        summary += f"\n各文件详情:\n"
        summary += f"{'-'*80}\n"

        for i, info in enumerate(file_info_list, 1):
            summary += f"{i}. 文件名: {info['file_name']}\n"
            if info['date']:
                summary += f"   日期: {info['date']}\n"
            summary += f"   新闻数量: {info['news_count']}条\n\n"

        summary += f"{'='*80}\n\n"

        f.write(summary)
        f.write("\n".join(all_content))

    print("\n" + "=" * 80)
    print(f"合并完成！")
    print(f"输出文件: {output_filename}")
    print(f"总新闻数量: {total_news}条")
    print("=" * 80)

if __name__ == "__main__":
    main()
