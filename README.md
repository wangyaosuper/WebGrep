# WebGrep - 智能新闻抓取与分析系统

## 项目概述

WebGrep是一个专业的新闻抓取与分析系统，专为智能驾驶行业设计。该系统能够从多个汽车行业网站自动抓取新闻内容，并利用大语言模型进行深度分析，生成结构化的行业分析报告。

### 核心功能

1. **多源新闻抓取**：支持从汽车之家、盖世汽车、IT之家、AutoNews等多个汽车行业网站抓取新闻
2. **智能内容提取**：自动识别并提取新闻标题、时间、链接和正文内容
3. **多线程处理**：采用多线程技术提高新闻抓取效率
4. **时间过滤**：支持按时间范围筛选新闻，只抓取指定时间之后的新闻
5. **新闻去重**：自动识别并删除标题和内容完全相同的重复新闻
6. **新闻合并**：支持将多个新闻文件合并为一个文件，并重新编号
7. **AI分析**：集成阿里云千问大模型，对新闻内容进行智能分析
8. **自定义分析**：支持用户自定义分析提示词，满足不同分析需求

## 系统架构

WebGrep系统由四个核心脚本组成：

### 1. WebGrep.py - 新闻抓取核心脚本

这是系统的核心脚本，负责从webarchive文件中提取新闻内容。

**主要功能：**
- 从webarchive文件中提取所有新闻链接
- 自动过滤非新闻链接（如图片、CSS、JS等资源）
- 从新闻链接中提取标题、时间和正文内容
- 支持多线程处理，提高效率
- 支持按时间过滤新闻

**支持的网站：**
- 汽车之家 (autohome.com.cn)
- 盖世汽车 (gasgoo.com)
- IT之家 (ithome.com)
- AutoNews (autonews.com)

**使用方法：**
```bash
# 处理单个或多个webarchive文件
python WebGrep.py file1.webarchive file2.webarchive

# 处理目录中的所有webarchive文件
python WebGrep.py --dir /path/to/webarchives

# 只抓取指定时间之后的新闻
python WebGrep.py --after "2025-01-01 00:00" file.webarchive

# 显示帮助信息
python WebGrep.py --help
```

### 2. AnalysisGrepOutput.py - 新闻分析脚本

该脚本负责对抓取的新闻进行智能分析，生成结构化的行业分析报告。

**主要功能：**
- 解析新闻文件，提取新闻信息
- 调用大语言模型进行智能分析
- 生成Markdown格式的分析报告
- 支持自定义分析提示词
- 支持多种大模型（qwen-plus、deepseek-v4-pro、qwen3.6-plus等）

**使用方法：**
```bash
# 使用默认模型(qwen-plus)分析新闻
python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md

# 指定模型分析新闻
python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --model deepseek-v4-pro

# 添加自定义分析要求
python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --custom-requirement "特别关注华为和小鹏的动态"
```

### 3. ConcatNews.py - 新闻合并脚本

该脚本用于将多个新闻文件合并为一个文件，并重新编号。

**主要功能：**
- 合并多个新闻文件
- 自动重新编号新闻条目
- 添加文件来源标记和日期信息
- 生成合并汇总报告

**使用方法：**
```bash
# 合并指定的新闻文件
python ConcatNews.py file1.txt file2.txt

# 合并work目录下的指定文件
python ConcatNews.py work/news_output_20260426_060455.txt work/news_output_20260428_052015.txt
```

### 4. DeduplicateNews.py - 新闻去重脚本

该脚本用于删除重复的新闻，重复的新闻是指新闻标题和内容都相同的新闻。

**主要功能：**
- 识别标题和内容完全相同的重复新闻
- 自动删除重复新闻
- 保留原始新闻并重新编号
- 生成去重报告

**使用方法：**
```bash
# 对新闻文件进行去重
python DeduplicateNews.py input.txt

# 指定输出文件路径
python DeduplicateNews.py work/news_output.txt -o output.txt
```

## 使用流程

### 第一步：保存网页

1. 通过Safari打开目标网站：
   - https://auto.ithome.com
   - https://www.autohome.com.cn
   - https://auto.gasgoo.com (需要手动点击到资讯栏目)
   - https://www.autonews.com

2. 确保页面内容完全加载

3. 使用Safari的"文件 > 导出为PDF"或"文件 > 存储为"功能，将网页保存为webarchive文件

### 第二步：抓取新闻

```bash
# 使用WebGrep.py从webarchive文件中抓取新闻
python WebGrep.py file1.webarchive file2.webarchive
```

抓取的新闻将保存到work目录下的news_output_YYYYMMDD_HHMMSS.txt文件中。
这里一般要使用 --dir 和 --after 两个参数

### 第三步：新闻处理（可选）

```bash
# 如果抓取了多个文件，可以合并它们
python ConcatNews.py work/news_output_20260426_060455.txt work/news_output_20260428_052015.txt

# 对新闻进行去重
python DeduplicateNews.py work/CONCAT_news_summary_20260426_120000.txt
```

### 第四步：分析新闻

```bash
# 使用AnalysisGrepOutput.py对新闻进行智能分析
python AnalysisGrepOutput.py work/DEDUPLICATED_CONCAT_news_summary_20260426_120000.txt --prompt-file prompts/weekly_news_summery.md
```

分析结果将保存为Markdown格式的报告文件。
这里一定要使用 --prompt-file, 并且常常要使用 --model参数， 我先在比较喜欢用 qwen3.6-plus这个模型

## 目录结构

```
WebGrep/
├── WebGrep.py              # 新闻抓取核心脚本
├── AnalysisGrepOutput.py   # 新闻分析脚本
├── ConcatNews.py           # 新闻合并脚本
├── DeduplicateNews.py      # 新闻去重脚本
├── prompts/                # 提示词模板目录
│   ├── daily_industry_launch.md
│   └── weekly_news_summery.md
├── work/                   # 工作目录，存放抓取和分析结果
├── archive/                # 归档目录
│   ├── daily/             # 每日归档
│   └── weekly/            # 每周归档
└── README.md              # 本文件
```

## 环境要求

- Python 3.7+
- 依赖库：
  - requests
  - beautifulsoup4
  - dashscope
  - openai

安装依赖：
```bash
pip install requests beautifulsoup4 dashscope openai
```

## 配置说明

### 环境变量配置

在使用AnalysisGrepOutput.py之前，需要配置阿里云API密钥：

```bash
# 在Linux/Mac上
export DASHSCOPE_API_KEY="your_api_key_here"

# 在Windows上
set DASHSCOPE_API_KEY=your_api_key_here
```

### 提示词模板

提示词模板存放在`prompts/`目录下，可以根据需要修改或创建新的模板。模板中支持以下变量：
- `{news_count}`: 新闻数量
- `{news_summary}`: 新闻摘要

## 版本说明

### 2026-05-06
- 新增支持国外网站AutoNews
- 优化新闻提取逻辑
- 改进多线程处理效率
WebGrep.v05@260506.支持国外网站AutoNews.py 和 AnalysisGrepOutput.v06@260502.支持模型从入參指定.支持通过openai调用百炼模型平台.py 是一组

### 2026-05-02 (V0.4.0)
WebGrep.v04@260430.支持设定抓取新闻的最早时间.支持autohome.py 和 AnalysisGrepOutput.v06@260502.支持模型从入參指定.支持通过openai调用百炼模型平台.py 是一组

### 2026-04-30
- 支持设定抓取新闻的最早时间
- 新增支持汽车之家网站
- 优化时间过滤功能
WebGrep.v04@260430.支持设定抓取新闻的最早时间.支持autohome.py 和  AnalysisGrepOutput.v05@260430.提示词解耦.支持行业每日发布.py 是一组

### 2026-04-20 （V0.3.0）
- 支持用户自定义提示词
- 改进新闻分析功能
- 优化输出格式
 WebGrep.v03@260420.py 和 AnalysisGrepOutput.v04@260420.支持用户定制提示词.py 是一组 支持用户定制提示词

### 2026-04-12
- 新增支持盖世汽车网站
- 扩展新闻上限和Tokens
- 增加Tesla特别关注
WebGrep.v02@260412.增加了盖世汽车共支持三个网站.py 和 AnalysisGrepOutput.v02@260412.py 是一组

### 2026-04-12
- 优化新闻提取逻辑
- 改进错误处理

### 2026-04-06
- 初始版本
- 支持IT之家和汽车之家网站
- 基本新闻抓取和分析功能

## 常见问题

### Q: 如何添加新的新闻网站支持？

A: 需要在WebGrep.py中添加针对新网站的新闻提取函数，并在`extract_links_from_file`函数中添加相应的处理逻辑。

### Q: 如何自定义分析报告的格式？

A: 可以修改`prompts/`目录下的提示词模板文件，或者创建新的模板文件，并在运行AnalysisGrepOutput.py时通过`--prompt-file`参数指定。

### Q: 新闻抓取失败怎么办？

A: 检查以下几点：
1. 确认webarchive文件是否正确保存
2. 检查网络连接是否正常
3. 查看控制台输出的错误信息

## 许可证

本项目仅供学习和研究使用。

## 联系方式

如有问题或建议，请通过项目仓库提交Issue。

