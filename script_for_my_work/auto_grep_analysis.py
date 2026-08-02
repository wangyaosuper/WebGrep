#!/usr/bin/env python3
"""
auto_grep_analysis.py - 一键完成新闻抓取、分析、重命名和PDF生成的日常工作脚本

使用方法:
    python script_for_my_work/auto_grep_analysis.py 260530
    python script_for_my_work/auto_grep_analysis.py 2026-05-30

参数说明:
    date_str: 日期字符串，支持两种格式:
        - 短格式: 260530 (用于--after参数和生成文件名)
        - 长格式: 2026-05-30 (会自动提取短格式部分用于文件名)

工作流程:
    1. 调用 WebGrep.py --dir cache --after <date> 抓取新闻
    2. 在 work 目录下找到最新生成的 dedup_news_output_*.txt 文件
    3. 调用 AnalysisGrepOutput.py 分析该文件
    4. 将生成的 _analysis.md 文件重命名为最终输出文件名（根据提示词模板自动决定）
    5. 调用 md2pdf.py 生成对应的 PDF 文件
    6. 对 dedup txt 文件进行 zip 压缩
"""

import sys
import os
import subprocess
import glob
import re
import time
from datetime import datetime
import shutil


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


def confirm_continue(message):
    if not sys.stdin.isatty():
        print(message)
        print("当前为非交互环境，自动继续执行。")
        return
    try:
        input(f"{message}\n按回车继续，或 Ctrl+C 终止：")
    except EOFError:
        print("未检测到交互输入（EOF），自动继续执行。")


def cleanup_intermediate_files(script_dir, work_dir, news_output_file, concat_files):
    print()
    print("=" * 60)
    print("📌 归档中间文件到 trash")
    print("=" * 60)

    moved = 0
    trash_dir = os.path.join(script_dir, "trash")
    os.makedirs(trash_dir, exist_ok=True)

    def move_to_trash(src_path):
        nonlocal moved
        if not os.path.exists(src_path):
            print(f"未找到（跳过）: {src_path}")
            return

        base_name = os.path.basename(src_path)
        dest_path = os.path.join(trash_dir, base_name)
        if os.path.exists(dest_path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            root, ext = os.path.splitext(base_name)
            dest_path = os.path.join(trash_dir, f"{root}.{ts}{ext}")

        shutil.move(src_path, dest_path)
        moved += 1
        print(f"已移动: {src_path} -> {dest_path}")

    if news_output_file:
        move_to_trash(news_output_file)
    else:
        print("未找到（跳过）: news_output_*.txt")

    for p in concat_files or []:
        move_to_trash(p)

    if moved == 0:
        print("未移动任何中间文件。")


def build_output_paths(work_dir, prompt_file, after_date, short_date):
    prompt_basename = os.path.basename(prompt_file or "")
    if prompt_basename == "weekly_news_summery.md":
        short_end = datetime.now().strftime("%y%m%d")
        md_name = f"智驾新闻摘要.{short_date}-{short_end}.md"
    else:
        md_name = f"产业每日发布.{short_date}.md"

    md_path = os.path.join(work_dir, md_name)
    pdf_path = os.path.splitext(md_path)[0] + ".pdf"
    return md_name, md_path, pdf_path


def copy_weekly_archive_txts(project_root, cache_dir, short_date, archive_daily_dir=None):
    archive_daily_dir = archive_daily_dir or os.path.abspath(
        os.path.join(project_root, "archive", "daily")
    )
    if not os.path.isdir(archive_daily_dir):
        print(f"⚠️  未找到归档目录，跳过历史txt拷贝: {archive_daily_dir}")
        return False

    try:
        short_date_int = int(short_date)
    except ValueError:
        print(f"⚠️  无法解析 short_date，跳过历史txt拷贝: {short_date}")
        return False

    print()
    print("=" * 60)
    print("📌 Weekly 模式：拷贝归档历史txt到缓存目录（用于补充输入）")
    print("=" * 60)
    print(f"归档目录: {archive_daily_dir}")
    print(f"缓存目录: {cache_dir}")
    print(f"起始日期: {short_date} (含当日及之后)")

    os.makedirs(cache_dir, exist_ok=True)
    dest_root = os.path.join(cache_dir, "_archive_daily")

    selected_dirs = []
    dir_pattern = re.compile(r"^work\.daily@(\d{6})$")
    for name in os.listdir(archive_daily_dir):
        full_path = os.path.join(archive_daily_dir, name)
        if not os.path.isdir(full_path):
            continue
        m = dir_pattern.match(name)
        if not m:
            continue
        try:
            dir_date_int = int(m.group(1))
        except ValueError:
            continue
        if dir_date_int >= short_date_int:
            selected_dirs.append((dir_date_int, name, full_path))

    selected_dirs.sort(key=lambda x: x[0])
    if not selected_dirs:
        print("未找到符合日期范围的归档目录，跳过拷贝。")
        return False

    copied_count = 0
    skipped_count = 0
    for _, subdir_name, src_dir in selected_dirs:
        for root, _, filenames in os.walk(src_dir):
            for filename in filenames:
                if not filename.lower().endswith(".txt"):
                    continue
                src_file = os.path.join(root, filename)
                dest_dir = os.path.join(dest_root, subdir_name)
                os.makedirs(dest_dir, exist_ok=True)
                dest_file = os.path.join(dest_dir, filename)
                if os.path.exists(dest_file):
                    skipped_count += 1
                    print(f"跳过（已存在）: {src_file} -> {dest_file}")
                    continue
                shutil.copy2(src_file, dest_file)
                copied_count += 1
                print(f"已拷贝: {src_file} -> {dest_file}")

    print(f"拷贝完成：新增 {copied_count} 个文件，跳过 {skipped_count} 个已存在文件。")
    return True


def get_news_output_path_from_analysis_input(analysis_input_file):
    base_dir = os.path.dirname(analysis_input_file or "")
    base_name = os.path.basename(analysis_input_file or "")
    if base_name.startswith("dedup_news_output_") and base_name.endswith(".txt"):
        news_name = base_name.replace("dedup_news_output_", "news_output_", 1)
        return os.path.join(base_dir, news_name)
    if base_name.startswith("news_output_") and base_name.endswith(".txt"):
        return analysis_input_file
    return None


def find_recent_files_by_pattern(search_dir, pattern, start_ts):
    candidates = glob.glob(os.path.join(search_dir, pattern))
    recent = []
    for p in candidates:
        try:
            if os.path.getmtime(p) >= start_ts - 1:
                recent.append(p)
        except OSError:
            continue
    recent.sort(key=os.path.getmtime)
    return recent


def main():
    import argparse
    epilog_text = (
        "示例用法:\n"
        "  python script_for_my_work/auto_grep_analysis.py 260530 --dir cache --prompt-file prompts/daily_industry_launch.md --model qwen3.6-plus\n"
        "  python script_for_my_work/auto_grep_analysis.py 2026-05-30 --dir cache --prompt-file prompts/daily_industry_launch.md --model qwen3.6-plus\n"
        "  python script_for_my_work/auto_grep_analysis.py --after 2026-05-30 --dir cache --prompt-file prompts/daily_industry_launch.md --model qwen3.6-plus\n"
        "  python script_for_my_work/auto_grep_analysis.py 260530 --dir cache --prompt-file prompts/daily_industry_launch.md --model qwen3.6-plus --custom-requirement \"特别关注华为和小鹏的动态\"\n"
        "  python script_for_my_work/auto_grep_analysis.py 260727 --dir cache --prompt-file prompts/weekly_news_summery.md --model qwen3.6-plus"
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
    parser.add_argument("--custom-requirement", "-c", help="添加用户定制化要求，用于补充大模型的提示词", default=None)

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

    final_md_name, final_md_path, final_pdf_path = build_output_paths(
        work_dir=work_dir,
        prompt_file=args.prompt_file,
        after_date=after_date,
        short_date=short_date,
    )

    print("🚀 自动化新闻抓取与分析流程启动")
    print(f"📅 日期参数: {date_str}")
    print(f"   --after 参数值: {after_date}")
    print(f"   输出文件名: {final_md_name}")

    prompt_basename = os.path.basename(args.prompt_file or "")
    if prompt_basename == "weekly_news_summery.md":
        did_copy = copy_weekly_archive_txts(
            project_root=project_root,
            cache_dir=cache_dir,
            short_date=short_date,
        )
        if did_copy:
            confirm_continue("✅ 归档历史txt拷贝完成，请确认输出无误后再开始抓取新闻（Step 1）")

    # ===== Step 1: 调用 WebGrep.py 抓取新闻 =====
    webgrep_script = os.path.join(project_root, "WebGrep.py")
    cmd_grep = [sys.executable, webgrep_script, "--dir", cache_dir, "--after", after_date]
    grep_start_ts = time.time()
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

    output_base_dir = os.path.dirname(dedup_file) or work_dir
    news_output_file = get_news_output_path_from_analysis_input(dedup_file)
    if not (news_output_file and os.path.exists(news_output_file)):
        recent_news = find_recent_files_by_pattern(output_base_dir, "news_output_*.txt", grep_start_ts)
        if recent_news:
            news_output_file = recent_news[-1]
        else:
            news_output_file = None
    concat_files = find_recent_files_by_pattern(output_base_dir, "CONCAT_news_summary_*.txt", grep_start_ts)

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
    # 如果有自定义要求，添加到命令中
    if args.custom_requirement:
        cmd_analysis.extend(["--custom-requirement", args.custom_requirement])
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

    cleanup_intermediate_files(
        script_dir=script_dir,
        work_dir=work_dir,
        news_output_file=news_output_file,
        concat_files=concat_files,
    )

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
