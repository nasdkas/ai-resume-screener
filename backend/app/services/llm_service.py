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
LLM_JSON_MODE = os.getenv('LLM_JSON_MODE', 'false').lower() in ('true', '1', 'yes')
LLM_THINK_MODE = os.getenv('LLM_THINK_MODE', 'false').lower() in ('true', '1', 'yes')

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


PARSE_JSON_SCHEMA = {
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
        "summary": {"type": "string", "description": "简历摘要，尽量详尽且不超300字"}
    },
    "required": ["name", "email", "phone", "skills", "experience", "education", "summary"]
}

MATCH_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "overallScore": {"type": "integer", "description": "综合评分0-100"},
        "skillMatch": {"type": "integer", "description": "技能匹配分0-100"},
        "experienceMatch": {"type": "integer", "description": "经验匹配分0-100"},
        "educationMatch": {"type": "integer", "description": "学历匹配分0-100"},
        "keywordMatch": {"type": "integer", "description": "关键词匹配分0-100"},
        "projectMatch": {"type": "integer", "description": "项目经验匹配分0-100"},
        "keywordMatches": {
            "type": "array",
            "items": {"type": "string"},
            "description": "简历满足的关键词"
        },
        "missingKeywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "简历不满足的关键词"
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "候选人优势"
        },
        "weaknesses": {
            "type": "array",
            "items": {"type": "string"},
            "description": "候选人不足"
        },
        "analysis": {"type": "string", "description": "匹配分析，详细评价不超350字"}
    },
    "required": ["overallScore", "skillMatch", "experienceMatch", "educationMatch",
                 "keywordMatch", "projectMatch", "keywordMatches", "missingKeywords",
                 "strengths", "weaknesses", "analysis"]
}


def _chat_completion(messages: list, temperature: float = 0.1, format: dict = None, think: bool = False) -> str:
    if LLM_PROVIDER == 'ollama':
        kwargs = {
            'model': MODEL,
            'messages': messages,
            'think': think,
            'options': {
                'temperature': temperature
            }
        }
        if format is not None:
            kwargs['format'] = format
        response = _ollama_client.chat(**kwargs)
        print("模型输出：")
        print(response)
        return response.message.content
    else:
        kwargs = {
            'model': MODEL,
            'messages': messages,
            'temperature': temperature
        }
        if format is not None:
            kwargs['response_format'] = {"type": "json_object"}
        response = _openai_client.chat.completions.create(**kwargs)
        print("模型输出：")
        print(response)
        return response.choices[0].message.content


async def _async_chat_completion(messages: list, temperature: float = 0.1, format: dict = None, think: bool = False) -> str:
    if LLM_PROVIDER == 'ollama':
        kwargs = {
            'model': MODEL,
            'messages': messages,
            'think': think,
            'options': {
                'temperature': temperature
            }
        }
        if format is not None:
            kwargs['format'] = format
        response = await _ollama_async_client.chat(**kwargs)
        print("模型输出：")
        print(response)
        return response.message.content
    else:
        kwargs = {
            'model': MODEL,
            'messages': messages,
            'temperature': temperature
        }
        if format is not None:
            kwargs['response_format'] = {"type": "json_object"}
        response = await _openai_async_client.chat.completions.create(**kwargs)
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


def _safe_float(value, default=0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        numbers = re.findall(r'[\d.]+', value)
        if numbers:
            try:
                return float(numbers[0])
            except ValueError:
                return default
    return default


def _calc_overall_score(skill: float, experience: float, keyword: float, project: float, education: float) -> int:
    return round(skill * 0.35 + experience * 0.20 + keyword * 0.20 + project * 0.15 + education * 0.10)


def _normalize_match_result(result: dict) -> Dict[str, Any]:
    skill = _safe_float(result.get('skillMatch'), 50)
    experience = _safe_float(result.get('experienceMatch'), 50)
    keyword = _safe_float(result.get('keywordMatch'), 50)
    project = _safe_float(result.get('projectMatch'), 50)
    education = _safe_float(result.get('educationMatch'), 50)
    llm_overall = _safe_float(result.get('overallScore'), None)
    # if llm_overall is not None and llm_overall <= 50:
    #     overall = int(llm_overall)
    # else:
    #     overall = _calc_overall_score(skill, experience, keyword, project, education)
    if llm_overall:
        overall = int(llm_overall)
    else:
        overall = _calc_overall_score(skill, experience, keyword, project, education)
    return {
        'overallScore': float(overall),
        'skillMatch': skill,
        'experienceMatch': experience,
        'keywordMatch': keyword,
        'projectMatch': project,
        'educationMatch': education,
        'keywordMatches': result.get('keywordMatches', []),
        'missingKeywords': result.get('missingKeywords', []),
        'strengths': result.get('strengths', []),
        'weaknesses': result.get('weaknesses', []),
        'analysis': result.get('analysis', '')
    }


PARSE_SYSTEM_MSG = """简历信息提取器，summary内容尽量完善且不超300字，简历中未提到相关内容时，填空。只输出JSON，不输出其他内容。
示例：李明，8年Java经验，精通Spring Boot、MySQL。本科，liming@example.com，13912345678。
输出：{"name":"李明","email":"liming@example.com","phone":"13912345678","skills":["Java","Spring Boot","MySQL"],"experience":8,"education":"本科","summary":"8年Java经验的工程师，精通Spring Boot、MySQL，硕士学历。"}"""

PARSE_PROMPT_TEMPLATE = """按示例格式提取。experience为纯数字，今天是{current_date}。

{resume_text}"""

MATCH_SYSTEM_MSG = """你是资深招聘匹配评估专家。你需要严格按评分规则对候选人进行客观评估。

评分维度与权重：
- skillMatch（技能匹配，权重35%）：候选人掌握的技能与JD要求的重合度，考虑技能深度与广度
- experienceMatch（经验匹配，权重20%）：与岗位相关的项目经验、行业经验，而非单纯工作年限
- keywordMatch（关键词匹配，权重20%）：简历中语义满足JD关键词的比例
- projectMatch（项目经验匹配，权重15%）：候选人过往项目与JD业务场景的相关性
- educationMatch（学历匹配，权重10%）：学历层次是否满足要求

评分规则：
1. 若候选人不满足【JD必须需求】中任意一项，overallScore打低分；只有完全满足所有必须需求时，才按上述权重加权计算overallScore并四舍五入
2. keywordMatches：简历语义满足的JD关键词（含近义词、上下位词匹配）
3. missingKeywords：简历明确不满足的JD关键词
4. strengths：列出候选人2-4个核心优势
5. weaknesses：列出候选人1-3个主要不足
6. analysis：综合评价，包含技能匹配分析、经验适配度、发展潜力，不超350字

注：今天是{current_date}
只输出JSON，不输出其他内容。"""

MATCH_PROMPT_TEMPLATE = """请严格按评分维度和权重评估候选人与岗位的匹配度。

【候选人简历】
{resume_text}

【职位描述】
{jd_description}

【JD必须需求】（硬性门槛，不满足任意一项则直接低分）
{scoring_criteria}

【JD关键词】
{keywords}

评估要求：
1. 仔细阅读简历，提取所有与JD相关的技能、经验和项目
2. keywordMatches只填JD关键词中简历满足的，missingKeywords只填不满足的
3. 关键词匹配要考虑语义：如JD要求"K8s"，简历提到"Kubernetes"算匹配
4. projectMatch重点看项目内容与JD业务的相关性，而非项目数量
5. **低分判定规则（最高优先级）**：
   - 逐条检查【JD必须需求】中的每一项
   - 只要任意一项在简历中明确不满足（或无法确认满足），则 **overallScore 直接打低分（满分 100 分）**，无需再执行下面的权重计算公式
   - 此时打分评语必须明确指出哪项必须需求不满足
6. 只有当候选人的简历 **完全满足所有【JD必须需求】** 时，才按以下公式计算 overallScore：
   - overallScore = skillMatch×0.35 + experienceMatch×0.20 + keywordMatch×0.20 + projectMatch×0.15 + educationMatch×0.10
   - 四舍五入取整，满分100分
7. 分数要有区分度，不要集中在中段：优秀候选人应得高分（≥80），明显不匹配必须需求的得低分（≤60），完全满足必须需求但其他方面偏弱的得中等分（61-79）"""

MERGE_PARSE_SYSTEM_MSG = """简历信息合并器，summary内容尽量完善且不超300字。只输出JSON，不输出其他内容。
将两份部分解析结果合并为一份完整结果，按示例格式输出。"""

MERGE_PARSE_PROMPT_TEMPLATE = """合并以下两份部分解析结果。skills取并集去重，experience取最大值，summary合并为更完整的描述，其余字段取非空值。

结果1：{first}
结果2：{second}"""

MERGE_MATCH_SYSTEM_MSG = """简历评估结果合并器。将两份部分匹配结果合并为一份完整结果。经验是指与岗位匹配的技能经验及相关项目经验，而非单纯工作年限；analysis内容详细不超350字。只输出JSON，不输出其他内容。"""

MERGE_MATCH_PROMPT_TEMPLATE = """合并以下两份部分匹配结果。

合并规则：
- skillMatch/experienceMatch/educationMatch/keywordMatch/projectMatch取最高分
- overallScore合并规则：
  - 如果两份结果都为低分，则合并为低分
  - 存在合格分后才按权重重算：skillMatch×0.35 + experienceMatch×0.20 + keywordMatch×0.20 + projectMatch×0.15 + educationMatch×0.10，四舍五入取整
- keywordMatches取并集去重
- missingKeywords只保留两份都缺失的
- strengths取并集去重，保留最多4条
- weaknesses取并集去重，保留最多3条
- analysis合并为更完整的评价
注：今天是{current_date}

结果1：{first}
结果2：{second}"""


MAX_PARSE_CHARS = 5000
MAX_MATCH_CHARS = 5000


def _format_scoring_criteria(criteria: list) -> str:
    if not criteria:
        return "无特殊要求，按默认权重评估(技能35%，经验20%，关键词20%，项目15%，学历10%)"
    lines = []
    for c in criteria:
        item = c.get('item', '') if isinstance(c, dict) else str(c)
        lines.append(f"- {item}")
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
    result_text = _clean_json_response(_chat_completion(messages, format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None))
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
    result_text = _clean_json_response(await _async_chat_completion(messages, format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None))
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


def _merge_split_keyword_results(first: Dict[str, Any], second: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    first_matched_lower = {kw.lower() for kw in first.get('keywordMatches', [])}
    second_matched_lower = {kw.lower() for kw in second.get('keywordMatches', [])}
    all_matched_lower = first_matched_lower | second_matched_lower
    all_keywords = list(dict.fromkeys(
        first.get('keywordMatches', []) + first.get('missingKeywords', []) +
        second.get('keywordMatches', []) + second.get('missingKeywords', [])
    ))
    merged_matched = []
    merged_missing = []
    for kw in all_keywords:
        if kw.lower() in all_matched_lower:
            merged_matched.append(kw)
        else:
            merged_missing.append(kw)
    return merged_matched, merged_missing


def _llm_merge_match(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    prompt = MERGE_MATCH_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False),
        current_date=datetime.datetime.now().date()
    )
    messages = [
        {"role": "system", "content": MERGE_MATCH_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(_chat_completion(messages, format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None, think=LLM_THINK_MODE))
    result = json.loads(result_text)
    merged_matched, merged_missing = _merge_split_keyword_results(first, second)
    result['keywordMatches'] = merged_matched
    result['missingKeywords'] = merged_missing
    return _normalize_match_result(result)


async def _async_llm_merge_match(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    prompt = MERGE_MATCH_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False),
        current_date=datetime.datetime.now().date()
    )
    messages = [
        {"role": "system", "content": MERGE_MATCH_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(await _async_chat_completion(messages, format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None, think=LLM_THINK_MODE))
    result = json.loads(result_text)
    merged_matched, merged_missing = _merge_split_keyword_results(first, second)
    result['keywordMatches'] = merged_matched
    result['missingKeywords'] = merged_missing
    return _normalize_match_result(result)


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
    result_text = _clean_json_response(_chat_completion(messages, format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None))
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
    result_text = _clean_json_response(await _async_chat_completion(messages, format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None))
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
        {"role": "system", "content": MATCH_SYSTEM_MSG.format(current_date=datetime.datetime.now().date())},
        {"role": "user", "content": prompt}
    ]
    result_text = _clean_json_response(_chat_completion(messages, format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None, think=LLM_THINK_MODE))
    result = json.loads(result_text)
    text_matched, text_missing = _match_keywords(keywords, resume_text)
    llm_matched = result.get('keywordMatches', [])
    llm_missing = result.get('missingKeywords', [])
    merged_matched, merged_missing = _merge_keyword_results(
        text_matched, text_missing, llm_matched, llm_missing, keywords
    )
    result['keywordMatches'] = merged_matched
    result['missingKeywords'] = merged_missing
    keyword_ratio = len(merged_matched) / len(keywords) * 100 if keywords else 100
    if not keywords:
        result['keywordMatch'] = 100
    else:
        result['keywordMatch'] = max(_safe_float(result.get('keywordMatch')), keyword_ratio)
    return _normalize_match_result(result)


async def _async_call_llm_match(resume_text: str, jd_description: str, keywords: list, scoring_criteria: list = None) -> Dict[str, Any]:
    prompt = MATCH_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        jd_description=jd_description,
        scoring_criteria=_format_scoring_criteria(scoring_criteria or []),
        keywords=','.join(keywords) if keywords else '无'
    )
    messages = [
        {"role": "system", "content": MATCH_SYSTEM_MSG.format(current_date=datetime.datetime.now().date())},
        {"role": "user", "content": prompt}
    ]
    print("评分提示词：")
    print(prompt)
    result_text = _clean_json_response(await _async_chat_completion(messages, format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None, think=LLM_THINK_MODE))
    result = json.loads(result_text)
    text_matched, text_missing = _match_keywords(keywords, resume_text)
    llm_matched = result.get('keywordMatches', [])
    llm_missing = result.get('missingKeywords', [])
    merged_matched, merged_missing = _merge_keyword_results(
        text_matched, text_missing, llm_matched, llm_missing, keywords
    )
    result['keywordMatches'] = merged_matched
    result['missingKeywords'] = merged_missing
    keyword_ratio = len(merged_matched) / len(keywords) * 100 if keywords else 100
    if not keywords:
        result['keywordMatch'] = 100
    else:
        result['keywordMatch'] = max(_safe_float(result.get('keywordMatch')), keyword_ratio)
    return _normalize_match_result(result)


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
