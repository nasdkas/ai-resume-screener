"""
测试 Ollama JSON 模式提取简历信息的效果
用法: 直接在 IDE 中运行，或 python test_json_mode.py <pdf路径>
"""

import os
import sys
import json
import time
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.parser import extract_text

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://192.168.8.103:11434')
MODELS = [os.getenv('OLLAMA_MODEL', 'gemma4:e4b')]

PDF_PATH = r'C:\Users\huai1\Desktop\【前端开发工程师_东莞 14-20K】李红阳 6年.pdf'

PARSE_SYSTEM_MSG = """简历信息提取器，summary内容尽量完善且不超250字，简历中未提到相关内容时，填空。只输出JSON，不输出其他内容。
示例：李明，8年Java经验，精通Spring Boot、MySQL。本科，liming@example.com，13912345678。
输出：{"name":"李明","email":"liming@example.com","phone":"13912345678","skills":["Java","Spring Boot","MySQL"],"experience":8,"education":"本科","summary":"8年Java经验的工程师，精通Spring Boot、MySQL，硕士学历。"}"""

PARSE_PROMPT_TEMPLATE = """按示例格式提取。experience为纯数字，今天是{current_date}。

{resume_text}"""

RESUME_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "姓名"},
        "email": {"type": "string", "description": "邮箱"},
        "phone": {"type": "string", "description": "手机号"},
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "技能列表"
        },
        "experience": {"type": "integer", "description": "工作年限"},
        "education": {"type": "string", "description": "学历"},
        "summary": {"type": "string", "description": "简历摘要，尽量详尽且不超过300字"}
    },
    "required": ["name", "email", "phone", "skills", "experience", "education", "summary"]
}


def test_normal_mode(ollama_client, model: str, resume_text: str) -> dict:
    prompt = PARSE_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        current_date=datetime.datetime.now().date()
    )
    messages = [
        {"role": "system", "content": PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    start = time.time()
    response = ollama_client.chat(
        model=model,
        messages=messages,
        # think=False,
        options={'temperature': 0.1}
    )
    elapsed = time.time() - start
    raw = response.message.content
    print("模型原始输出：")
    print(response)
    return {"raw": raw, "elapsed": elapsed}


def test_json_mode(ollama_client, model: str, resume_text: str) -> dict:
    prompt = PARSE_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        current_date=datetime.datetime.now().date()
    )
    messages = [
        {"role": "system", "content": PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    start = time.time()
    response = ollama_client.chat(
        model=model,
        messages=messages,
        think=False,
        format=RESUME_JSON_SCHEMA,
        options={'temperature': 0.1}
    )
    elapsed = time.time() - start
    raw = response.message.content
    print("模型原始输出：")
    print(response)
    return {"raw": raw, "elapsed": elapsed}


def try_parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        import re
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw_preview": text[:200]}


def main():
    if len(sys.argv) >= 2:
        pdf_path = sys.argv[1]
    else:
        pdf_path = PDF_PATH

    if not os.path.isfile(pdf_path):
        print(f"文件不存在: {pdf_path}")
        sys.exit(1)

    print(f"=== 解析 PDF: {pdf_path} ===\n")
    filename = os.path.basename(pdf_path)
    with open(pdf_path, 'rb') as f:
        file_bytes = f.read()

    resume_text = extract_text(file_bytes, filename)
    print(f"提取文本长度: {len(resume_text)} 字符")
    print(f"文本预览:\n{resume_text[:500]}")
    print("\n" + "=" * 60 + "\n")

    import ollama
    client = ollama.Client(host=OLLAMA_HOST)

    for model in MODELS:
        print(f"\n{'#' * 60}")
        print(f"# 模型: {model}")
        print(f"{'#' * 60}\n")

        # for mode_name, test_fn in [("普通模式", test_normal_mode), ("JSON模式", test_json_mode)]:
        for mode_name, test_fn in [("JSON模式", test_json_mode)]:
            print(f"--- {mode_name} ---")
            try:
                result = test_fn(client, model, resume_text)
                parsed = try_parse_json(result["raw"])
                has_error = "_parse_error" in parsed

                print(f"耗时: {result['elapsed']:.2f}s")
                print(f"JSON解析: {'失败' if has_error else '成功'}")
                if has_error:
                    print(f"错误: {parsed['_parse_error']}")
                    print(f"原始输出预览: {parsed['_raw_preview']}")
                else:
                    print(f"解析结果:")
                    print(json.dumps(parsed, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"调用失败: {e}")

            print()

    print("\n=== 测试完成 ===")


if __name__ == '__main__':
    main()
