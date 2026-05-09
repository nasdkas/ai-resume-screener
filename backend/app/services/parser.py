import io
import re
import unicodedata
from typing import Optional, List, Tuple

import pdfplumber
from PyPDF2 import PdfReader
from docx import Document


def _calc_text_quality(text: str) -> float:
    if not text or not text.strip():
        return 0.0

    total_chars = len(text.replace(' ', '').replace('\n', ''))
    if total_chars == 0:
        return 0.0

    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', text))
    meaningful_words = re.findall(r'[A-Za-z]{2,}|\d{2,}', text)
    meaningful_len = sum(len(w) for w in meaningful_words)
    meaningful_ratio = (cjk_chars + meaningful_len) / total_chars

    bad_chars = len(re.findall(
        r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ue000-\uf8ff]', text
    ))
    bad_ratio = bad_chars / total_chars

    lines = [l for l in text.splitlines() if l.strip()]
    if lines:
        good_lines = sum(1 for l in lines if not _is_garbled_line(l))
        line_quality = good_lines / len(lines)
    else:
        line_quality = 0.0

    length_bonus = min(1.0, total_chars / 500)

    score = (meaningful_ratio * 0.4
             + line_quality * 0.3
             + length_bonus * 0.1
             - bad_ratio * 0.5)
    return max(0.0, min(1.0, score))


def _is_garbled_line(line: str) -> bool:
    stripped = re.sub(r'\s+', '', line)
    if not stripped:
        return False

    if re.search(r'[\u4e00-\u9fff]', stripped):
        return False

    if len(stripped) <= 2:
        if re.match(r'^[A-Z]{2}$', stripped):
            return False
        if re.match(r'^\d{4}$', stripped):
            return False
        return True

    if len(stripped) <= 4:
        if stripped.isdigit() and len(stripped) >= 4:
            return False
        if re.findall(r'[A-Za-z]{3,}', stripped):
            return False
        if re.match(r'^[\+\-\*/\.\|#@]$', stripped):
            return False
        return True

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


def _normalize_unicode(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)

    replacements = {
        '\u00a0': ' ',
        '\u3000': ' ',
        '\u2002': ' ',
        '\u2003': ' ',
        '\u2009': ' ',
        '\u200a': ' ',
        '\u200b': '',
        '\u200c': '',
        '\u200d': '',
        '\u00ad': '',
        '\u2028': '\n',
        '\u2029': '\n',
        '\ufeff': '',
        '\u200e': '',
        '\u200f': '',
        '\u202a': '',
        '\u202b': '',
        '\u202c': '',
        '\u202d': '',
        '\u202e': '',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'[\ue000-\uf8ff\U000f0000-\U0010ffff]', '', text)

    return text


def _remove_inline_garbage(line: str) -> str:
    line = re.sub(r'[A-Za-z0-9\-_~`^]{20,}', '', line)

    line = re.sub(r'(?<=[\u4e00-\u9fff])[A-Za-z0-9\-_~`^]{8,}(?=[\u4e00-\u9fff])', '', line)
    line = re.sub(r'(?<=[\u4e00-\u9fff])[A-Za-z0-9\-_~`^]{8,}$', '', line)
    line = re.sub(r'^[A-Za-z0-9\-_~`^]{8,}(?=[\u4e00-\u9fff])', '', line)

    line = re.sub(r'(?<=\d)[A-Za-z](?=\d)', '', line)

    return line


def _purify_line(line: str) -> str:
    line = _remove_inline_garbage(line)

    line = re.sub(r'(?<![a-zA-Z0-9])[~`^]+(?![a-zA-Z0-9])', '', line)

    if re.search(r'[\u4e00-\u9fff]', line):
        line = re.sub(r'^(?:[A-Za-z\d](?:\s+|$))+?(?=[\u4e00-\u9fff])', '', line)
        line = re.sub(r'(?<=[\u4e00-\u9fff])(?:\s+[A-Za-z\d])+$', '', line)
        line = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', line)

    line = re.sub(r'\s+', ' ', line).strip()
    return line


def _is_fragment_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if re.search(r'[\u4e00-\u9fff]{2,}', stripped):
        return False

    meaningful_words = re.findall(r'[A-Za-z]{3,}', stripped)
    if meaningful_words:
        return False

    if re.search(r'[\u4e00-\u9fff]', stripped) and len(stripped) > 4:
        return False

    if len(stripped) <= 2:
        return True

    tokens = re.split(r'\s+', stripped)
    short_tokens = [t for t in tokens if len(t) <= 2]
    if len(tokens) > 0 and len(short_tokens) / len(tokens) > 0.7 and len(tokens) >= 2:
        return True

    return False


def _clean_garbled_text(text: str) -> str:
    text = _normalize_unicode(text)

    lines = text.splitlines()
    cleaned = []

    for raw_line in lines:
        if not raw_line.strip():
            cleaned.append('')
            continue

        line = raw_line.rstrip('\n\r')
        has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', line))

        if has_cjk:
            cleaned.append(_purify_line(line))
        else:
            if not _is_garbled_line(line):
                cleaned.append(_purify_line(line))

    cleaned = _remove_fragment_clusters(cleaned)
    result = _merge_broken_paragraphs(cleaned)
    result = re.sub(r'\n{2,}', '\n', result)
    return result


def _remove_fragment_clusters(lines: List[str]) -> List[str]:
    if not lines:
        return lines

    result = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            result.append(lines[i])
            i += 1
            continue

        if not _is_fragment_line(lines[i]):
            result.append(lines[i])
            i += 1
            continue

        fragment_count = 0
        j = i
        while j < len(lines):
            if not lines[j].strip():
                break
            if _is_fragment_line(lines[j]):
                fragment_count += 1
                j += 1
            else:
                if fragment_count >= 2:
                    break
                result.append(lines[i])
                i += 1
                fragment_count = 0
                break

        if fragment_count >= 2:
            i = j
        elif fragment_count > 0 and i < len(lines) and _is_fragment_line(lines[i]):
            i = j

    return result


def _merge_broken_paragraphs(lines: List[str]) -> str:
    if not lines:
        return ""

    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            merged.append('')
            i += 1
            continue

        current = line
        while i + 1 < len(lines):
            next_line = lines[i + 1]
            if not next_line.strip():
                break
            if re.search(r'[。！？；\.\!\?;]$', current):
                break
            if re.search(r'^[\u4e00-\u9fff]', next_line) and re.search(r'[\u4e00-\u9fff]$', current):
                current = current + next_line
                i += 1
            else:
                break

        merged.append(current)
        i += 1

    return '\n'.join(merged)


def _extract_pages_pdfplumber(file_bytes: bytes) -> List[str]:
    pages = []
    try:
        with io.BytesIO(file_bytes) as pdf_stream:
            with pdfplumber.open(pdf_stream) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(
                        x_tolerance=3,
                        y_tolerance=3,
                        layout=True,
                        x_density=6.5,
                        y_density=13,
                    )
                    if not page_text or not page_text.strip():
                        page_text = page.extract_text(
                            x_tolerance=3,
                            y_tolerance=3,
                        )
                    pages.append(page_text or "")
    except Exception as e:
        raise RuntimeError(f"pdfplumber 解析失败: {e}")
    return pages


def _extract_pages_pymupdf(file_bytes: bytes) -> List[str]:
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF 未安装")
    pages = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            flags = (
                fitz.TEXT_PRESERVE_WHITESPACE
                | fitz.TEXT_DEHYPHENATE
                | fitz.TEXT_MEDIABOX_CLIP
            )
            page_text = page.get_text("text", flags=flags, sort=True)
            pages.append(page_text or "")
        doc.close()
    except Exception as e:
        raise RuntimeError(f"PyMuPDF 解析失败: {e}")
    return pages


def _extract_pages_pypdf2(file_bytes: bytes) -> List[str]:
    pages = []
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            pages.append(page.extract_text() or "")
    except Exception as e:
        raise RuntimeError(f"PyPDF2 解析失败: {e}")
    return pages


def _extract_pdf_multi_engine(file_bytes: bytes) -> str:
    page_candidates: dict = {}

    engines = [
        ("pdfplumber", _extract_pages_pdfplumber),
        ("pymupdf", _extract_pages_pymupdf),
        ("pypdf2", _extract_pages_pypdf2),
    ]

    for engine_name, extract_fn in engines:
        try:
            pages = extract_fn(file_bytes)
            for i, page_text in enumerate(pages):
                if page_text and page_text.strip():
                    quality = _calc_text_quality(page_text)
                    if i not in page_candidates:
                        page_candidates[i] = []
                    page_candidates[i].append((page_text, quality, engine_name))
        except Exception:
            continue

    if not page_candidates:
        return ""

    max_page = max(page_candidates.keys())
    best_pages = []
    for i in range(max_page + 1):
        if i in page_candidates:
            candidates = page_candidates[i]
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_pages.append(candidates[0][0])

    return "\n\n".join(best_pages).strip()


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
        raw_text = _extract_pdf_multi_engine(file_bytes)
        return _clean_garbled_text(raw_text)
    elif filename_lower.endswith('.docx'):
        return extract_text_from_docx(file_bytes)
    elif filename_lower.endswith('.txt'):
        return file_bytes.decode('utf-8', errors='ignore')
    return None


if __name__ == '__main__':
    import os
    import sys

    file_path = r'C:\Users\huai1\Desktop\【前端开发工程师_东莞 14-20K】李红阳 6年.pdf'

    if len(sys.argv) >= 2:
        file_path = sys.argv[1]

    if not os.path.isfile(file_path):
        print(f"文件不存在: {file_path}")
        sys.exit(1)

    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    result = extract_text(file_bytes, filename)
    print(result)
    print(f"\n--- 文本长度: {len(result)} 字符 ---")
