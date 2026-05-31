#!/usr/bin/env python3
"""
auto_grep_analysis.py - 一键完成新闻抓取、分析、重命名和PDF生成的日常工作脚本

使用方法:
    python script_for_my_work/auto_grep_analysis.py 260530
    python script_for_my_work/auto_grep_analysis.py 2026-05-30

参数说明:
    date_str: 日期字符串，支持两种格式:
        - 短格式: 260530 (用于--after参数和生成文件名，如 产业每日发布.260530.md)
        - 长格式: 2026-05-30 (会自动提取短格式部分用于文件名)

工作流程:
    1. 调用 WebGrep.py --dir cache --after <date> 抓取新闻
    2. 在 work 目录下找到最新生成的 dedup_news_output_*.txt 文件
    3. 调用 AnalysisGrepOutput.py 分析该文件
    4. 将生成的 _analysis.md 文件重命名为 产业每日发布.<短日期>.md
    5. 调用 md2pdf.py 生成对应的 PDF 文件
    6. 对 dedup txt 文件进行 zip 压缩
"""

import sys
import os
import subprocess
import glob
import re
import time


def parse_date_arg(date_str):
    """
    解析日期参数，返回 (after_date, short_date)
    - after_date: 用于 --after 参数，格式 2026-05-30
    - short_date: 用于文件名，格式 260530
    """
    # 尝试匹配长格式 2026-05-30
    long_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if long_match:
        after_date = date_str
        short_date = date_str[2:].replace('-', '')  # 260530
        return after_date, short_date

    # 尝试匹配短格式 260530
    short_match = re.match(r'^(\d{6})$', date_str)
    if short_match:
        short_date = date_str
        # 还原为长格式
        after_date = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
        return after_date, short_date

    print(f"错误: 无法解析日期参数 '{date_str}'")
    print("支持的格式: 260530 或 2026-05-30")
    sys.exit(1)


def find_latest_dedup_file(work_dir):
    """在 work 目录下找到最新生成的 dedup_news_output_*.txt 文件"""
    pattern = os.path.join(work_dir, "dedup_news_output_*.txt")
    files = glob.glob(pattern)
    if not files:
        return None
    # 按修改时间排序，取最新的
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def run_command(cmd, description):
    """运行shell命令并打印信息"""
    print()
    print("=" * 60)
    print(f"📌 {description}")
    print(f"🔧 执行命令: {' '.join(cmd)}")
    print("=" * 60)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"⚠️  命令执行失败，返回码: {result.returncode}")
        return False
    print(f"✅ {description} 完成")
    return True


def main():
    import argparse
    epilog_text = (
        "示例用法:\n"
        "  python script_for_my_work/auto_grep_analysis.py 260530 --dir cache --prompt-file prompts/daily_industry_launch.md --model qwen3.6-plus\n"
        "  python script_for_my_work/auto_grep_analysis.py 2026-05-30 --dir cache --prompt-file prompts/daily_industry_launch.md --model qwen3.6-plus\n"
        "  python script_for_my_work/auto_grep_analysis.py --after 2026-05-30 --dir cache --prompt-file prompts/daily_industry_launch.md --model qwen3.6-plus"
    )
    parser = argparse.ArgumentParser(
        description="一键完成新闻抓取、分析、重命名和PDF生成的日常工作脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog_text
    )
    parser.add_argument("date", nargs="?", help="日期字符串，支持短格式(260530)或长格式(2026-05-30)")
    parser.add_argument("--after", help="指定抓取新闻的起始日期，支持短格式(260530)或长格式(2026-05-30)")
    parser.add_argument("--dir", required=True, help="WebGrep.py 的 --dir 参数，指定 webarchive 缓存目录")
    parser.add_argument("--prompt-file", required=True, help="AnalysisGrepOutput.py 的 --prompt-file 参数，指定提示词模板文件")
    parser.add_argument("--model", required=True, help="AnalysisGrepOutput.py 的 --model 参数，指定使用的模型名称")

    args = parser.parse_args()

    # 兼容 --after 和位置参数两种写法
    date_str = args.after or args.date
    if not date_str:
        parser.print_help()
        sys.exit(1)

    after_date, short_date = parse_date_arg(date_str)

    # 脚本所在目录（work 目录在此目录下）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 项目根目录（WebGrep.py、AnalysisGrepOutput.py、prompts/ 在此目录下）
    project_root = os.path.dirname(script_dir)
    # work 目录约定在 script_dir 下
    work_dir = os.path.join(script_dir, "work")
    # --dir 参数：WebGrep.py 的缓存目录
    cache_dir = args.dir

    # 最终输出文件名
    final_md_name = f"产业每日发布.{short_date}.md"
    final_md_path = os.path.join(work_dir, final_md_name)
    final_pdf_path = os.path.join(work_dir, f"产业每日发布.{short_date}.pdf")

    print("🚀 自动化新闻抓取与分析流程启动")
    print(f"📅 日期参数: {date_str}")
    print(f"   --after 参数值: {after_date}")
    print(f"   输出文件名: {final_md_name}")

    # ===== Step 1: 调用 WebGrep.py 抓取新闻 =====
    webgrep_script = os.path.join(project_root, "WebGrep.py")
    cmd_grep = [sys.executable, webgrep_script, "--dir", cache_dir, "--after", after_date]
    if not run_command(cmd_grep, "Step 1/5: 抓取新闻 (WebGrep.py)"):
        print("❌ 新闻抓取失败，流程终止")
        sys.exit(1)

    # ===== Step 2: 找到最新生成的 dedup 文件 =====
    print()
    print("=" * 60)
    print("📌 Step 2/5: 查找去重后的新闻文件")
    print("=" * 60)

    # 等待一下确保文件系统同步
    time.sleep(1)

    dedup_file = find_latest_dedup_file(work_dir)
    if not dedup_file:
        print("⚠️  未在 work 目录下找到 dedup_news_output_*.txt 文件")
        print("   尝试查找普通 news_output_*.txt 文件...")
        pattern = os.path.join(work_dir, "news_output_*.txt")
        files = glob.glob(pattern)
        if not files:
            print("❌ 也未找到 news_output_*.txt 文件，流程终止")
            sys.exit(1)
        files.sort(key=os.path.getmtime, reverse=True)
        dedup_file = files[0]
        print(f"   使用文件: {dedup_file}")
    else:
        print(f"✅ 找到去重文件: {dedup_file}")

    # ===== Step 3: 调用 AnalysisGrepOutput.py 分析新闻 =====
    analysis_script = os.path.join(project_root, "AnalysisGrepOutput.py")
    prompt_file = args.prompt_file
    model = args.model
    cmd_analysis = [
        sys.executable, analysis_script,
        dedup_file,
        "--prompt-file", prompt_file,
        "--model", model
    ]
    if not run_command(cmd_analysis, "Step 3/5: 分析新闻 (AnalysisGrepOutput.py)"):
        print("❌ 新闻分析失败，流程终止")
        sys.exit(1)

    # ===== Step 4: 重命名分析结果文件 =====
    print()
    print("=" * 60)
    print("📌 Step 4/5: 重命名分析结果文件")
    print("=" * 60)

    # 分析后的文件名: dedup_news_output_XXXX_analysis.md
    analysis_md = dedup_file.replace('.txt', '_analysis.md')
    if not os.path.exists(analysis_md):
        # 如果路径不对，尝试在 work 目录下查找
        base_name = os.path.basename(dedup_file).replace('.txt', '_analysis.md')
        analysis_md = os.path.join(work_dir, base_name)

    if not os.path.exists(analysis_md):
        print(f"❌ 未找到分析结果文件: {analysis_md}")
        sys.exit(1)

    print(f"   原文件: {analysis_md}")
    print(f"   目标文件: {final_md_path}")

    # 如果目标文件已存在，先删除
    if os.path.exists(final_md_path):
        os.remove(final_md_path)
        print(f"   已删除旧文件: {final_md_path}")

    os.rename(analysis_md, final_md_path)
    print(f"✅ 重命名完成: {final_md_name}")

    # ===== Step 5: 调用 md2pdf.py 生成 PDF =====
    md2pdf_script = os.path.join(os.path.dirname(project_root), "md2pdf", "md2pdf.py")
    if not os.path.exists(md2pdf_script):
        # 尝试其他可能的路径
        alt_path = os.path.join(project_root, "..", "md2pdf", "md2pdf.py")
        if os.path.exists(alt_path):
            md2pdf_script = alt_path

    cmd_pdf = [sys.executable, md2pdf_script, final_md_path]
    if not run_command(cmd_pdf, "Step 5/5: 生成 PDF (md2pdf.py)"):
        print("⚠️  PDF 生成失败，但其他步骤已完成")

    # ===== 附加: 压缩 dedup txt 文件 =====
    print()
    print("=" * 60)
    print("📌 附加: 压缩去重后的新闻文件")
    print("=" * 60)

    dedup_basename = os.path.basename(dedup_file)
    zip_name = f"{dedup_basename}.zip"
    zip_path = os.path.join(work_dir, zip_name)

    cmd_zip = ["zip", "-j", zip_path, dedup_file]
    result = subprocess.run(cmd_zip, cwd=work_dir)
    if result.returncode == 0:
        print(f"✅ 压缩完成: {zip_name}")
    else:
        print("⚠️  压缩失败（zip 命令可能不可用）")

    # ===== 完成 =====
    print()
    print("🎉" * 20)
    print("🎉 全部流程完成！")
    print(f"📄 Markdown 报告: {final_md_path}")
    if os.path.exists(final_pdf_path):
        print(f"📑 PDF 报告: {final_pdf_path}")
    print(f"📦 压缩文件: {zip_path}")
    print("🎉" * 20)


if __name__ == "__main__":
    main()
