import sys
import os
import re
import argparse
from dashscope import Generation
import dashscope
from openai import OpenAI

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

def load_prompt_template(prompt_file):
    """从文件加载提示词模板"""
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()

def create_analysis_prompt(news_list, custom_requirement=None, prompt_template=None):
    """创建分析提示词"""
    # 分析所有新闻，不设置上限
    selected_news = news_list

    # 构建新闻摘要
    news_summary = ""
    for i, news in enumerate(selected_news, 1):
        news_summary += f"\n新闻 {i}:\n"
        news_summary += f"标题: {news['title']}\n"
        news_summary += f"链接: {news['link']}\n"
        news_summary += f"内容摘要: {news['content'][:1500]}...\n"  # 只使用前1500字

    # 使用外部提示词模板或默认模板
    if prompt_template:
        # 替换模板变量
        prompt = prompt_template.replace('{news_count}', str(len(selected_news)))
        prompt = prompt.replace('{news_summary}', news_summary)
    else:
        # 如果没有提供模板，使用默认的硬编码模板
        prompt = f"""你是一位专业的行业分析师，请对以下{len(selected_news)}篇科技新闻围绕智能驾驶进行深入分析。

{news_summary}

请按照以下要求围绕智能驾驶生成一份结构化的Markdown格式分析报告：
1. **整体概述**
   - 总结整体趋势
2. **关键看点**
   - 提取3-5个关键看点
3. **总结与建议**
   - 提供行业建议"""

    # 如果用户提供了定制化要求，添加到提示词中
    if custom_requirement:
        prompt = f"用户定制要求：{custom_requirement}\n\n{prompt}"

    return prompt

def call_qwen_plus(prompt, model='qwen-plus'):
    """调用阿里云大模型（使用原生SDK）"""
    # 从环境变量获取API密钥
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")

    dashscope.api_key = api_key

    response = Generation.call(
        model=model,
        prompt=prompt,
        max_tokens=32000,
        temperature=0.7,
    )

    if response.status_code == 200:
        return response.output.text
    else:
        raise Exception(f"API调用失败: {response.message}")

def call_model_via_openai(prompt, model, system_message):
    """通过OpenAI兼容接口调用模型（支持deepseek-v4-pro、qwen3.6-plus等）"""
    # 从环境变量获取API密钥
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")

    # 初始化客户端
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    # 发起对话请求
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        stream=False
    )

    # 返回模型的回复内容
    return completion.choices[0].message.content

def call_deepseek_v4_pro(prompt, model='deepseek-v4-pro'):
    """调用阿里云百炼的deepseek-v4-pro模型"""
    return call_model_via_openai(prompt, model, "你是一位专业的行业分析师。")

def call_qwen3_6_plus(prompt, model='qwen3.6-plus'):
    """调用阿里云百炼的qwen3.6-plus模型"""
    return call_model_via_openai(prompt, model, "你是一位专业的行业分析师。")

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
  python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md
  python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --model qwen-plus
  python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --model deepseek-v4-pro
  python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --model qwen3.6-plus
  python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --custom-requirement "特别关注华为和小鹏的动态"
  python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --model deepseek-v4-pro --custom-requirement "重点关注激光雷达技术发展"
  python AnalysisGrepOutput.py news.txt --prompt-file prompts/weekly_news_summery.md --model qwen3.6-plus --custom-requirement "重点关注激光雷达技术发展"
        '''
    )
    parser.add_argument('input_file', help='要分析的新闻文件路径')
    parser.add_argument('--prompt-file', '-p',
                       help='指定提示词模板文件路径（必填）',
                       required=True)
    parser.add_argument('--model', '-m',
                       help='指定使用的模型名称（默认: qwen-plus，可选: deepseek-v4-pro, qwen3.6-plus）',
                       default='qwen-plus')
    parser.add_argument('--custom-requirement', '-c', 
                       help='添加用户定制化要求，用于补充大模型的提示词',
                       default=None)

    # 如果没有参数，显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()
    input_file = args.input_file
    prompt_file = args.prompt_file
    model = args.model
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

    # 加载提示词模板
    if not os.path.exists(prompt_file):
        print(f"错误: 提示词文件 '{prompt_file}' 不存在")
        return
    print(f"正在加载提示词模板 '{prompt_file}'...")
    try:
        prompt_template = load_prompt_template(prompt_file)
        print("提示词模板加载成功")
    except Exception as e:
        print(f"错误: 加载提示词模板失败: {str(e)}")
        return

    # 创建分析提示词
    print("正在创建分析提示词...")
    if custom_requirement:
        print(f"用户定制要求: {custom_requirement}")
    prompt = create_analysis_prompt(news_list, custom_requirement, prompt_template)

    # 调用大模型进行分析
    print(f"正在调用大模型 '{model}' 进行分析...")
    try:
        # 根据模型名称选择调用不同的函数
        # 对于特定模型使用专用函数，其他模型默认使用OpenAI兼容接口
        if model.startswith('deepseek'):
            analysis = call_deepseek_v4_pro(prompt, model)
        elif model.startswith('qwen3.6'):
            analysis = call_qwen3_6_plus(prompt, model)
        elif model == 'qwen-plus':
            analysis = call_qwen_plus(prompt, model)
        else:
            # 未知模型默认使用OpenAI兼容接口
            print(f"提示: 使用OpenAI兼容接口调用模型 '{model}'")
            analysis = call_model_via_openai(prompt, model, "你是一位专业的行业分析师。")
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
