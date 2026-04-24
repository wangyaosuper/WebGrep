
import sys
import os
import re
from dashscope import Generation
import dashscope

def parse_news_file(filename):
    """解析新闻文件，提取所有新闻信息"""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # 使用正则表达式分割每条新闻
    news_pattern = r'===== 新闻 (\d+) ====='
    news_sections = re.split(news_pattern, content)

    news_list = []
    for i in range(1, len(news_sections), 2):
        if i+1 < len(news_sections):
            news_num = news_sections[i]
            news_content = news_sections[i+1]

            # 提取标题
            title_match = re.search(r'标题: (.+)', news_content)
            title = title_match.group(1).strip() if title_match else "未知标题"

            # 提取时间
            time_match = re.search(r'时间: (.+)', news_content)
            news_time = time_match.group(1).strip() if time_match else "未知时间"

            # 提取链接
            link_match = re.search(r'链接: (.+)', news_content)
            link = link_match.group(1).strip() if link_match else ""

            # 提取内容
            content_match = re.search(r'内容:\n(.+)', news_content, re.DOTALL)
            news_text = content_match.group(1).strip() if content_match else ""

            news_list.append({
                'title': title,
                'time': news_time,
                'link': link,
                'content': news_text
            })

    return news_list

def create_analysis_prompt(news_list):
    """创建分析提示词"""
    # 限制新闻数量，避免提示词过长
    max_news = 50
    selected_news = news_list[:max_news]

    # 构建新闻摘要
    news_summary = ""
    for i, news in enumerate(selected_news, 1):
        news_summary += f"\n新闻 {i}:\n"
        news_summary += f"标题: {news['title']}\n"
        news_summary += f"链接: {news['link']}\n"
        news_summary += f"内容摘要: {news['content'][:500]}...\n"  # 只使用前500字

    prompt = f"""你是一位专业的行业分析师，请对以下{len(selected_news)}篇科技新闻围绕智能驾驶进行深入分析。

{news_summary}

请按照以下要求围绕智能驾驶生成一份结构化的Markdown格式分析报告：

1. **整体概述**
   - 围绕智能驾驶，总结这些新闻的整体趋势和主要方向
   - 围绕智能驾驶，指出当前科技行业的热点领域

2. **主题分类**
   - 围绕智能驾驶，将新闻按主题分类
   - 每个主题下列出相关新闻要点
   - 为每个要点提供原新闻链接，格式为：[新闻标题](链接)

3. **关键看点**
   - 围绕智能驾驶，提取最重要的3-5个关键看点
   - 每个看点详细说明其重要性
   - 提供支撑该看点的新闻链接

4. **公司动态**
   - 围绕智能驾驶，按公司分类总结各公司的最新动态
   - 重点突出技术创新、产品发布、战略合作等
   - 提供相关新闻链接

5. **技术趋势**
   - 围绕智能驾驶，分析当前技术发展趋势
   - 围绕智能驾驶，预测未来可能的发展方向
   - 提供支撑分析的新闻链接

6. **市场影响**
   - 分析这些新闻对市场的影响
   - 指出潜在的投资机会和风险
   - 提供相关新闻链接

7. **总结与建议**
   - 总结整体分析结果
   - 提供对行业从业者的建议
   - 指出值得关注的方向

请确保报告结构清晰，语言专业，便于读者快速获取关键信息。所有新闻链接都应使用Markdown格式：[新闻标题](链接)"""

    return prompt

def call_qwen_plus(prompt):
    """调用阿里云qwen-plus大模型"""
    # 从环境变量获取API密钥
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")

    dashscope.api_key = api_key

    response = Generation.call(
        model='qwen-plus',
        prompt=prompt,
        max_tokens=4000,
        temperature=0.7,
    )

    if response.status_code == 200:
        return response.output.text
    else:
        raise Exception(f"API调用失败: {response.message}")

def save_markdown_report(content, output_file):
    """保存Markdown格式报告"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    if len(sys.argv) < 2:
        print("使用方法: python AnalysisGrepOutput.py <新闻输出文件>")
        return

    input_file = sys.argv[1]

    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        return

    # 解析新闻文件
    print(f"正在解析文件 '{input_file}'...")
    news_list = parse_news_file(input_file)
    print(f"找到 {len(news_list)} 条新闻")

    if not news_list:
        print("未找到任何新闻")
        return

    # 创建分析提示词
    print("正在创建分析提示词...")
    prompt = create_analysis_prompt(news_list)

    # 调用大模型进行分析
    print("正在调用大模型进行分析...")
    try:
        analysis = call_qwen_plus(prompt)
    except Exception as e:
        print(f"分析失败: {str(e)}")
        return

    # 保存报告
    output_file = input_file.replace('.txt', '_analysis.md')
    print(f"正在保存报告到 '{output_file}'...")
    save_markdown_report(analysis, output_file)
    print(f"完成! 分析报告已保存到 '{output_file}'")

if __name__ == "__main__":
    main()
