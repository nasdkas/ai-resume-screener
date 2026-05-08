import io
from typing import Optional
from PyPDF2 import PdfReader
from docx import Document
import pdfplumber


#!/usr/bin/env python3
"""
清洗 PDF 解析乱码：
- 删除孤立单字符行（除非是中文）
- 过滤随机字母/数字长串
- 合并剩余内容，保留中文和短单词
"""

import re
import sys
from pathlib import Path

import re
from typing import Optional

# ---------- 清洗相关辅助函数 ----------

def is_garbled_line(line: str) -> bool:
    stripped = re.sub(r'\s+', '', line)
    if not stripped:
        return False

    # 如果是纯数字且长度 >= 4（如年份 "2023"），则保留（视为有意义）
    if stripped.isdigit() and len(stripped) >= 4:
        return False

    # 极短行（≤4 字符）仍然丢弃，因为乱码碎片居多
    if len(stripped) <= 4:
        return True

    # 其余规则不变
    if len(stripped) > 30 and ' ' not in line:
        return True
    words = re.findall(r'[A-Za-z]{2,}', stripped)
    digits = re.findall(r'\d+', stripped)
    if not words and not digits:
        return True
    meaningful_len = sum(len(w) for w in words) + sum(len(d) for d in digits)
    ratio = meaningful_len / len(stripped) if stripped else 0
    if ratio < 0.3 and len(stripped) < 20:
        return True
    tokens = re.findall(r'[^\s\-]+', stripped)
    if tokens and all(len(tok) == 1 for tok in tokens) and len(tokens) > 2:
        return True
    return False


def purify_line(line: str) -> str:
    # 基础净化
    line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', line)
    line = re.sub(r'[\ue000-\uf8ff\U000f0000-\U0010ffff]', '', line)
    line = re.sub(r'(?<![a-zA-Z0-9])[~`^]+(?![a-zA-Z0-9])', '', line)

    if re.search(r'[\u4e00-\u9fff]', line):
        # 1. 删除行首连续单字母/数字碎片
        line = re.sub(r'^(?:[A-Za-z\d](?:\s+|$))+?(?=[\u4e00-\u9fff])', '', line)
        # 2. 删除行尾连续单字母/数字碎片
        line = re.sub(r'(?<=[\u4e00-\u9fff])(?:\s+[A-Za-z\d])+$', '', line)
        # 3. 删除中文后直接紧跟的长乱码串（≥15个字母数字符号）
        line = re.sub(r'([\u4e00-\u9fff])([A-Za-z0-9\-_~]{15,})', r'\1', line)

    line = re.sub(r'\s+', ' ', line).strip()
    return line


def clean_garbled_text_preserve_layout(text: str) -> str:
    """
    仅删除乱码行，严格保留原换行和段落布局。
    - 包含中文的行直接保留（行内净化）
    - 不含中文的行用启发式规则判断，是乱码则整行丢弃
    - 空行保留（表示段落间距）
    """
    lines = text.splitlines()
    cleaned = []

    for raw_line in lines:
        if not raw_line.strip():  # 空行保留
            cleaned.append('')
            continue

        line = raw_line.rstrip('\n\r')
        has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', line))

        if has_cjk:
            cleaned.append(purify_line(line))
        else:
            if not is_garbled_line(line):
                cleaned.append(purify_line(line))
            # 乱码行直接丢弃，不添加任何内容

    return '\n'.join(cleaned)


def extract_text_from_pdf_plumber(file_bytes: bytes) -> str:
    """使用 pdfplumber 提取 PDF 文本（对复杂排版/表格/扫描件文字提取更稳定）"""
    text_parts = []
    try:
        with io.BytesIO(file_bytes) as pdf_stream:
            with pdfplumber.open(pdf_stream) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
    except Exception as e:
        raise RuntimeError(f"pdfplumber 解析 PDF 失败: {e}")
    return "\n\n".join(text_parts).strip()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    pdf_stream = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_stream)
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def extract_text_from_docx(file_bytes: bytes) -> str:
    text = ""
    docx_stream = io.BytesIO(file_bytes)
    doc = Document(docx_stream)
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text


def extract_text(file_bytes: bytes, filename: str) -> Optional[str]:
    filename_lower = filename.lower()
    if filename_lower.endswith('.pdf'):
        # return clean_garbled_text_preserve_layout(extract_text_from_pdf_plumber(file_bytes))
        return clean_garbled_text_preserve_layout(extract_text_from_pdf(file_bytes))
    elif filename_lower.endswith('.docx'):
        return extract_text_from_docx(file_bytes)
    elif filename_lower.endswith('.txt'):
        return file_bytes.decode('utf-8', errors='ignore')
    return None


if __name__ == '__main__':
    import os

    file_path = r'C:\Users\huai1\Desktop\【java工程师_东莞 15-25K】杨远红 10年以上.pdf'
    # file_path = r"D:\简历-樊昊.pdf"
    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    # 提取文本
    result = extract_text(file_bytes, filename)
    print(result)
