import sys
import os
import re
import argparse
from dashscope import Generation
import dashscope

def parse_news_file(filename):
    """解析新闻文件，提取所有新闻信息"""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # 去除多余的空行（连续多个空行替换为单个空行）
    content = re.sub(r'\n\s*\n+', '\n\n', content)

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

def create_analysis_prompt(news_list, custom_requirement=None):
    """创建分析提示词"""
    # 分析所有新闻，不设置上限
    selected_news = news_list

    # 构建新闻摘要
    news_summary = ""
    for i, news in enumerate(selected_news, 1):
        news_summary += f"\n新闻 {i}:\n"
        news_summary += f"标题: {news['title']}\n"
        news_summary += f"链接: {news['link']}\n"
        news_summary += f"内容摘要: {news['content'][:500]}...\n"  # 只使用前500字

    # 构建基础提示词
    prompt = f"""你是一位专业的汽车行业分析师，请对以下{len(selected_news)}篇关于北京车展（全称：北京国际汽车展览会）的新闻进行深入分析。

特别要求：
1. 必须聚焦且仅仅聚焦北京国际汽车展览会（北京车展）和各车企发布会进行分析
2. 必须包含所有重要车企的发布会内容，包括但不限于产品发布、技术展示、战略发布等
3. 深入分析车展和发布会反映的行业趋势

{news_summary}

请按照以下要求生成一份结构化的Markdown格式分析报告：

1. **北京车展整体概述**
   - 总结本届北京车展的整体规模、主题和亮点
   - 分析车展反映出的汽车行业整体趋势和主要方向
   - 指出本届车展与往届相比的新变化和新特点

2. **北京车展关键看点**
   - 提取本届北京车展最重要的5-8个关键看点
   - 每个看点详细给出分析说明，包括产品、技术、市场等方面
   - 提供支撑该看点的新闻链接

3. **各车企发布会深度分析**
   - 按车企分类总结各车企在北京车展期间的发布会内容
   - 重点突出：新车发布、技术展示、战略发布、合作动态等
   - 分析各车企的市场定位和竞争策略
   - 提供相关新闻链接

4. **行业趋势分析**
   - 从车展和发布会内容分析当前汽车行业发展趋势
   - 重点分析：新能源、智能化、网联化、共享化等方向
   - 分析价格战、市场格局变化等行业热点
   - 提供支撑分析的新闻链接

5. **技术趋势与创新亮点**
   - 分析车展上展示的最新技术趋势
   - 重点包括：智能驾驶、电池技术、智能座舱、车联网等
   - 预测未来可能的技术发展方向
   - 提供支撑分析的新闻链接

6. **市场影响与竞争格局**
   - 分析车展和发布会内容对汽车市场的影响
   - 分析各品牌的市场表现和竞争态势
   - 指出潜在的市场机会和挑战
   - 提供相关新闻链接

7. **总结与建议**
   - 总结北京车展的整体分析结果
   - 提供对汽车行业从业者的建议
   - 指出未来值得关注的重点方向

请确保报告结构清晰，语言专业，便于读者快速获取关键信息。所有新闻链接都应使用Markdown格式：[新闻标题](链接)"""

    # 如果用户提供了定制化要求，添加到提示词中
    if custom_requirement:
        prompt = prompt.replace(
            "请按照以下要求围绕智能驾驶生成一份结构化的Markdown格式分析报告：",
            f"用户定制要求：{custom_requirement}\n\n请按照以下要求围绕智能驾驶生成一份结构化的Markdown格式分析报告："
        )

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
        max_tokens=16000,
        temperature=0.7,
    )

    if response.status_code == 200:
        return response.output.text
    else:
        raise Exception(f"API调用失败: {response.message}")

def save_markdown_report(content, output_file):
    """保存Markdown格式报告"""
    # 添加CSS样式
    css_style = """<style>
table {
    border-collapse: collapse;
    width: 100%;
    margin: 20px 0;
    font-size: 14px;
}
th, td {
    border: 1px solid #ddd;
    padding: 12px;
    text-align: left;
}
th {
    background-color: #f5f5f5;
    font-weight: bold;
}
tr:nth-child(even) {
    background-color: #f9f9f9;
}
tr:hover {
    background-color: #f0f0f0;
}
</style>
"""

    # AI生成声明
    ai_notice = """# ⚠️ 声明

**本报告由AI生成，仅供参考。**

---

"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(css_style)
        f.write(ai_notice)
        f.write(content)

def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(
        description='分析新闻文件并生成智能驾驶行业分析报告',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例用法:
  python AnalysisGrepOutput.v04@260420.py news.txt
  python AnalysisGrepOutput.v04@260420.py news.txt --custom-requirement "特别关注华为和小鹏的动态"
  python AnalysisGrepOutput.v04@260420.py news.txt --custom-requirement "重点关注激光雷达技术发展"
        '''
    )
    parser.add_argument('input_file', help='要分析的新闻文件路径')
    parser.add_argument('--custom-requirement', '-c', 
                       help='添加用户定制化要求，用于补充大模型的提示词',
                       default=None)

    # 如果没有参数，显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()
    input_file = args.input_file
    custom_requirement = args.custom_requirement

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
    if custom_requirement:
        print(f"用户定制要求: {custom_requirement}")
    prompt = create_analysis_prompt(news_list, custom_requirement)

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
