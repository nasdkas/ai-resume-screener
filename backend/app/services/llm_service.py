import os
import json
import re
import asyncio
from typing import Dict, Any, List, Tuple
from dotenv import load_dotenv
import datetime

load_dotenv()

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai').lower()
MODEL = os.getenv('LLM_MODEL', 'qwen3.5:2b')

if LLM_PROVIDER == 'ollama':
    import ollama

    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    _ollama_client = ollama.Client(host=OLLAMA_HOST)
    _ollama_async_client = ollama.AsyncClient(host=OLLAMA_HOST)
else:
    from openai import OpenAI, AsyncOpenAI

    _openai_client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY'),
        base_url=os.getenv('OPENAI_BASE_URL')
    )
    _openai_async_client = AsyncOpenAI(
        api_key=os.getenv('OPENAI_API_KEY'),
        base_url=os.getenv('OPENAI_BASE_URL')
    )


def _chat_completion(messages: list, temperature: float = 0.1) -> str:
    if LLM_PROVIDER == 'ollama':
        response = _ollama_client.chat(
            model=MODEL,
            messages=messages,
            think=False,
            options={
                'temperature': temperature
            }
        )
        print("模型输出：")
        print(response)
        return response.message.content
    else:
        response = _openai_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature
        )
        print("模型输出：")
        print(response)
        return response.choices[0].message.content


async def _async_chat_completion(messages: list, temperature: float = 0.1) -> str:
    if LLM_PROVIDER == 'ollama':
        response = await _ollama_async_client.chat(
            model=MODEL,
            messages=messages,
            think=False,
            options={
                'temperature': temperature
            }
        )
        print("模型输出：")
        print(response)
        return response.message.content
    else:
        response = await _openai_async_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature
        )
        print("模型输出：")
        print(response)
        return response.choices[0].message.content


def _clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith('```'):
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text


def _safe_int(value, default=0) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        numbers = re.findall(r'\d+', value)
        if numbers:
            return int(numbers[0])
    return default


PARSE_SYSTEM_MSG = """简历信息提取器，summary内容尽量完善且不超250字，简历中未提到相关内容时，填空。只输出JSON，不输出其他内容。
示例：李明，8年Java经验，精通Spring Boot、MySQL。本科，liming@example.com，13912345678。
输出：{"name":"李明","email":"liming@example.com","phone":"13912345678","skills":["Java","Spring Boot","MySQL"],"experience":8,"education":"本科","summary":"8年Java经验的工程师，精通Spring Boot、MySQL，硕士学历。"}"""

PARSE_PROMPT_TEMPLATE = """按示例格式提取。experience为纯数字，今天是{current_date}。

{resume_text}"""

MATCH_SYSTEM_MSG = """招聘匹配评估专家，经验是指与岗位匹配的技能经验及相关项目经验，而不单只工作年限；analysis内容尽量完善且不超250字。只输出JSON，不输出其他内容。
示例：{"overallScore":75,"skillMatch":80,"experienceMatch":70,"educationMatch":90,"keywordMatches":["Java","MySQL"],"missingKeywords":["K8s"],"analysis":"技能匹配良好，缺少K8s经验。经验满足要求。学历符合。"}"""

MATCH_PROMPT_TEMPLATE = """按示例格式评估。overallScore侧重技能(70%)，学历权重极低，分数0-100整数。keywordMatches为简历语义满足的关键词，missingKeywords为简历不满足的关键词。

简历：{resume_text}

JD：{jd_description}

评分标准：{scoring_criteria}

关键词：{keywords}"""

MERGE_PARSE_SYSTEM_MSG = """简历信息合并器，summary内容尽量完善且不超250字。只输出JSON，不输出其他内容。
将两份部分解析结果合并为一份完整结果，按示例格式输出。"""

MERGE_PARSE_PROMPT_TEMPLATE = """合并以下两份部分解析结果。skills取并集去重，experience取最大值，summary合并为更完整的描述，其余字段取非空值。

结果1：{first}
结果2：{second}"""

MERGE_MATCH_SYSTEM_MSG = """匹配结果合并器，经验是指与岗位匹配的技能经验及相关项目经验，而不单只工作年限；analysis内容尽量完善且不超250字。只输出JSON，不输出其他内容。
将两份部分匹配结果合并为一份完整结果，按示例格式输出。"""

MERGE_MATCH_PROMPT_TEMPLATE = """合并以下两份部分匹配结果。skillMatch/experienceMatch/educationMatch取最高分，overallScore按合并结果重算，着重技能与项目经验匹配，keywordMatches取并集去重，missingKeywords只保留两份都缺失的，analysis合并为更完整的评价。

结果1：{first}
结果2：{second}"""


MAX_PARSE_CHARS = 4000
MAX_MATCH_CHARS = 3000


def _format_scoring_criteria(criteria: list) -> str:
    if not criteria:
        return "无特殊要求，按默认权重评估(技能70%，经验20%，学历10%)"
    lines = []
    for c in criteria:
        item = c.get('item', '') if isinstance(c, dict) else str(c)
        weight = c.get('weight', '重要') if isinstance(c, dict) else '重要'
        if weight == '必须':
            lines.append(f"【必须】{item}：不满足则该项打极低分")
        elif weight == '加分':
            lines.append(f"【加分】{item}：满足则适当加分，不满足不扣分")
        else:
            lines.append(f"【重要】{item}：显著影响评分")
    return '\n'.join(lines)


def _should_split(text_len: int, threshold: int) -> bool:
    if LLM_PROVIDER != 'ollama':
        return False
    return text_len > threshold


def _split_resume(text: str) -> Tuple[str, str]:
    mid = len(text) // 2
    split_pos = text.rfind('\n', 0, mid)
    if split_pos == -1:
        split_pos = mid
    return text[:split_pos], text[split_pos:]



def _llm_merge_parse(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    prompt = MERGE_PARSE_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False)
    )
    messages = [
        {"role": "system", "content": MERGE_PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(_chat_completion(messages))
    result = json.loads(result_text)
    return {
        'name': result.get('name', first.get('name', '未知')),
        'email': result.get('email', first.get('email', '')),
        'phone': result.get('phone', first.get('phone', '')),
        'skills': result.get('skills', first.get('skills', [])),
        'experience': _safe_int(result.get('experience'), first.get('experience', 0)),
        'education': result.get('education', first.get('education', '')),
        'summary': result.get('summary', first.get('summary', ''))
    }


async def _async_llm_merge_parse(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    prompt = MERGE_PARSE_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False)
    )
    messages = [
        {"role": "system", "content": MERGE_PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(await _async_chat_completion(messages))
    result = json.loads(result_text)
    return {
        'name': result.get('name', first.get('name', '未知')),
        'email': result.get('email', first.get('email', '')),
        'phone': result.get('phone', first.get('phone', '')),
        'skills': result.get('skills', first.get('skills', [])),
        'experience': _safe_int(result.get('experience'), first.get('experience', 0)),
        'education': result.get('education', first.get('education', '')),
        'summary': result.get('summary', first.get('summary', ''))
    }


def _llm_merge_match(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    prompt = MERGE_MATCH_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False)
    )
    messages = [
        {"role": "system", "content": MERGE_MATCH_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(_chat_completion(messages))
    result = json.loads(result_text)
    return {
        'overallScore': float(result.get('overallScore', 50)),
        'skillMatch': float(result.get('skillMatch', 50)),
        'experienceMatch': float(result.get('experienceMatch', 50)),
        'educationMatch': float(result.get('educationMatch', 50)),
        'keywordMatches': result.get('keywordMatches', first.get('keywordMatches', [])),
        'missingKeywords': result.get('missingKeywords', first.get('missingKeywords', [])),
        'analysis': result.get('analysis', first.get('analysis', ''))
    }


async def _async_llm_merge_match(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    prompt = MERGE_MATCH_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False)
    )
    messages = [
        {"role": "system", "content": MERGE_MATCH_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(await _async_chat_completion(messages))
    result = json.loads(result_text)
    return {
        'overallScore': float(result.get('overallScore', 50)),
        'skillMatch': float(result.get('skillMatch', 50)),
        'experienceMatch': float(result.get('experienceMatch', 50)),
        'educationMatch': float(result.get('educationMatch', 50)),
        'keywordMatches': result.get('keywordMatches', first.get('keywordMatches', [])),
        'missingKeywords': result.get('missingKeywords', first.get('missingKeywords', [])),
        'analysis': result.get('analysis', first.get('analysis', ''))
    }


def _contains_cjk(text: str) -> bool:
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff':
            return True
    return False


def _match_keywords(keywords: List[str], resume_text: str) -> Tuple[List[str], List[str]]:
    keyword_matches = []
    missing_keywords = []
    resume_lower = resume_text.lower()
    for kw in keywords:
        kw_lower = kw.lower()
        kw_words = kw_lower.split()
        if len(kw_words) > 1:
            if all(w in resume_lower for w in kw_words):
                keyword_matches.append(kw)
            else:
                missing_keywords.append(kw)
        elif _contains_cjk(kw):
            if kw_lower in resume_lower:
                keyword_matches.append(kw)
            else:
                missing_keywords.append(kw)
        else:
            pattern = r'\b' + re.escape(kw_lower) + r'\b'
            if re.search(pattern, resume_lower):
                keyword_matches.append(kw)
            else:
                missing_keywords.append(kw)
    return keyword_matches, missing_keywords


def match_keywords_in_resume(keywords: List[str], resume_text: str) -> Dict[str, List[str]]:
    if not keywords:
        return {'keywordMatches': [], 'missingKeywords': []}
    matched, missing = _match_keywords(keywords, resume_text)
    return {'keywordMatches': matched, 'missingKeywords': missing}


def _merge_keyword_results(text_matched: List[str], text_missing: List[str],
                           llm_matched: List[str], llm_missing: List[str],
                           all_keywords: List[str]) -> Tuple[List[str], List[str]]:
    text_matched_lower = {kw.lower() for kw in text_matched}
    llm_matched_lower = {kw.lower() for kw in llm_matched}
    merged_matched = []
    merged_missing = []
    for kw in all_keywords:
        kw_lower = kw.lower()
        if kw_lower in text_matched_lower or kw_lower in llm_matched_lower:
            merged_matched.append(kw)
        else:
            merged_missing.append(kw)
    return merged_matched, merged_missing


def _call_llm_parse(resume_text: str) -> Dict[str, Any]:
    prompt = PARSE_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        current_date=datetime.datetime.now().date()
    )
    messages = [
        {"role": "system", "content": PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(_chat_completion(messages))
    result = json.loads(result_text)
    return {
        'name': result.get('name', '未知'),
        'email': result.get('email', ''),
        'phone': result.get('phone', ''),
        'skills': result.get('skills', []),
        'experience': _safe_int(result.get('experience'), 0),
        'education': result.get('education', ''),
        'summary': result.get('summary', '')
    }


async def _async_call_llm_parse(resume_text: str) -> Dict[str, Any]:
    prompt = PARSE_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        current_date=datetime.datetime.now().date()
    )
    messages = [
        {"role": "system", "content": PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(await _async_chat_completion(messages))
    result = json.loads(result_text)
    return {
        'name': result.get('name', '未知'),
        'email': result.get('email', ''),
        'phone': result.get('phone', ''),
        'skills': result.get('skills', []),
        'experience': _safe_int(result.get('experience'), 0),
        'education': result.get('education', ''),
        'summary': result.get('summary', '')
    }


def parse_resume_with_llm(resume_text: str) -> Dict[str, Any]:
    try:
        if not _should_split(len(resume_text), MAX_PARSE_CHARS):
            return _call_llm_parse(resume_text)

        first_half, second_half = _split_resume(resume_text)
        first_result = _call_llm_parse(first_half)
        second_result = _call_llm_parse(second_half)
        return _llm_merge_parse(first_result, second_result)
    except Exception as e:
        print(f"LLM解析错误: {e}")
        raise RuntimeError(f"简历解析失败: {e}")


def _call_llm_match(resume_text: str, jd_description: str, keywords: list, scoring_criteria: list = None) -> Dict[str, Any]:
    prompt = MATCH_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        jd_description=jd_description,
        scoring_criteria=_format_scoring_criteria(scoring_criteria or []),
        keywords=','.join(keywords) if keywords else '无'
    )
    messages = [
        {"role": "system", "content": MATCH_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(_chat_completion(messages))
    result = json.loads(result_text)
    text_matched, text_missing = _match_keywords(keywords, resume_text)
    llm_matched = result.get('keywordMatches', [])
    llm_missing = result.get('missingKeywords', [])
    merged_matched, merged_missing = _merge_keyword_results(
        text_matched, text_missing, llm_matched, llm_missing, keywords
    )
    return {
        'overallScore': float(result.get('overallScore', 50)),
        'skillMatch': float(result.get('skillMatch', 50)),
        'experienceMatch': float(result.get('experienceMatch', 50)),
        'educationMatch': float(result.get('educationMatch', 50)),
        'keywordMatches': merged_matched,
        'missingKeywords': merged_missing,
        'analysis': result.get('analysis', '')
    }


async def _async_call_llm_match(resume_text: str, jd_description: str, keywords: list, scoring_criteria: list = None) -> Dict[str, Any]:
    prompt = MATCH_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        jd_description=jd_description,
        scoring_criteria=_format_scoring_criteria(scoring_criteria or []),
        keywords=','.join(keywords) if keywords else '无'
    )
    messages = [
        {"role": "system", "content": MATCH_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    print("match prompt：")
    print(messages)
    result_text = _clean_json_response(await _async_chat_completion(messages))
    result = json.loads(result_text)
    text_matched, text_missing = _match_keywords(keywords, resume_text)
    llm_matched = result.get('keywordMatches', [])
    llm_missing = result.get('missingKeywords', [])
    merged_matched, merged_missing = _merge_keyword_results(
        text_matched, text_missing, llm_matched, llm_missing, keywords
    )
    return {
        'overallScore': float(result.get('overallScore', 50)),
        'skillMatch': float(result.get('skillMatch', 50)),
        'experienceMatch': float(result.get('experienceMatch', 50)),
        'educationMatch': float(result.get('educationMatch', 50)),
        'keywordMatches': merged_matched,
        'missingKeywords': merged_missing,
        'analysis': result.get('analysis', '')
    }


def match_resume_with_jd(resume_text: str, jd_description: str, keywords: list, scoring_criteria: list = None) -> Dict[str, Any]:
    try:
        if not _should_split(len(resume_text), MAX_MATCH_CHARS):
            return _call_llm_match(resume_text, jd_description, keywords, scoring_criteria)

        first_half, second_half = _split_resume(resume_text)
        first_result = _call_llm_match(first_half, jd_description, keywords, scoring_criteria)
        second_result = _call_llm_match(second_half, jd_description, keywords, scoring_criteria)
        return _llm_merge_match(first_result, second_result)
    except Exception as e:
        print(f"LLM匹配错误: {e}")
        raise RuntimeError(f"简历匹配失败: {e}")


async def async_parse_resume_with_llm(resume_text: str) -> Dict[str, Any]:
    try:
        if not _should_split(len(resume_text), MAX_PARSE_CHARS):
            return await _async_call_llm_parse(resume_text)

        first_half, second_half = _split_resume(resume_text)
        first_result, second_result = await asyncio.gather(
            _async_call_llm_parse(first_half),
            _async_call_llm_parse(second_half)
        )
        return await _async_llm_merge_parse(first_result, second_result)
    except Exception as e:
        print(f"LLM异步解析错误: {e}")
        raise RuntimeError(f"简历解析失败: {e}")


async def async_match_resume_with_jd(resume_text: str, jd_description: str, keywords: list, scoring_criteria: list = None) -> Dict[str, Any]:
    try:
        if not _should_split(len(resume_text), MAX_MATCH_CHARS):
            return await _async_call_llm_match(resume_text, jd_description, keywords, scoring_criteria)

        first_half, second_half = _split_resume(resume_text)
        first_result, second_result = await asyncio.gather(
            _async_call_llm_match(first_half, jd_description, keywords, scoring_criteria),
            _async_call_llm_match(second_half, jd_description, keywords, scoring_criteria)
        )
        return await _async_llm_merge_match(first_result, second_result)
    except Exception as e:
        print(f"LLM异步匹配错误: {e}")
        raise RuntimeError(f"简历匹配失败: {e}")
