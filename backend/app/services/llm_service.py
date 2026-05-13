import os
import json
import re
import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv
import datetime

logger = logging.getLogger(__name__)

from .scoring import (
    SCORING_VERSION, DIMENSIONS, DIMENSION_KEYS, SCORE_BANDS,
    HARD_THRESHOLD_CAP,
    calc_overall_score, clamp_score, get_score_band, calc_confidence,
    format_dimensions_for_prompt, format_bands_for_prompt,
    format_anchors_for_prompt, format_weights_for_prompt,
)

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

# ── JSON Schemas ──────────────────────────────────────────────────────

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

THRESHOLD_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "evidence": {"type": "string"}
                },
                "required": ["criterion", "passed", "evidence"]
            }
        },
        "allPassed": {"type": "boolean"}
    },
    "required": ["checks", "allPassed"]
}

# ── LLM API helpers ───────────────────────────────────────────────────

def _chat_completion(messages: list, temperature: float = 0.1, format: dict = None, think: bool = False) -> str:
    if LLM_PROVIDER == 'ollama':
        kwargs = {
            'model': MODEL,
            'messages': messages,
            'think': think,
            'options': {'temperature': temperature}
        }
        if format is not None:
            kwargs['format'] = format
        response = _ollama_client.chat(**kwargs)
        logger.debug("模型输出：")
        logger.debug(response)
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
        logger.debug("模型输出：")
        logger.debug(response)
        return response.choices[0].message.content


async def _async_chat_completion(messages: list, temperature: float = 0.1, format: dict = None, think: bool = False) -> str:
    if LLM_PROVIDER == 'ollama':
        kwargs = {
            'model': MODEL,
            'messages': messages,
            'think': think,
            'options': {'temperature': temperature}
        }
        if format is not None:
            kwargs['format'] = format
        response = await _ollama_async_client.chat(**kwargs)
        logger.debug("模型输出：")
        logger.debug(response)
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
        logger.debug("模型输出：")
        logger.debug(response)
        return response.choices[0].message.content


# ── Utility functions ─────────────────────────────────────────────────

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


def _safe_json_parse(text: str, context: str = "") -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM 返回了非法的 JSON (context: {context}): {e}\n原始响应前200字符: {text[:200]}"
        ) from e


def _contains_cjk(text: str) -> bool:
    for ch in text:
        if '一' <= ch <= '鿿' or '぀' <= ch <= 'ゟ' or '゠' <= ch <= 'ヿ':
            return True
    return False


# ── Text splitting (Ollama only) ──────────────────────────────────────

MAX_PARSE_CHARS = 5000
MAX_MATCH_CHARS = 5000


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


# ── Scoring criteria formatting ───────────────────────────────────────

def _format_scoring_criteria(criteria: list) -> str:
    if not criteria:
        return "无特殊要求，按默认权重评估"
    lines = [f"- {c.get('item', '') if isinstance(c, dict) else str(c)}" for c in criteria]
    return "【必须满足】（任意一项不满足则直接低分）：\n" + '\n'.join(lines)


def _get_must_have_criteria(scoring_criteria: list) -> list:
    """Extract must-have criteria items."""
    if not scoring_criteria:
        return []
    return [
        c.get('item', '') if isinstance(c, dict) else str(c)
        for c in scoring_criteria
    ]


# ── Normalization ─────────────────────────────────────────────────────

def _normalize_match_result(result: dict, must_have_failed: bool = False,
                            text_quality: float = 1.0, resume_char_count: int = 0,
                            was_split: bool = False,
                            threshold_passed: Optional[bool] = None,
                            llm_threshold_match: Optional[bool] = None) -> Dict[str, Any]:
    """Normalize and clamp scores, optionally apply threshold cap, compute confidence."""
    skill = clamp_score(_safe_float(result.get('skillMatch'), 0))
    experience = clamp_score(_safe_float(result.get('experienceMatch'), 0))
    keyword = clamp_score(_safe_float(result.get('keywordMatch'), 0))
    project = clamp_score(_safe_float(result.get('projectMatch'), 0))
    education = clamp_score(_safe_float(result.get('educationMatch'), 0))

    if must_have_failed:
        skill = min(skill, HARD_THRESHOLD_CAP)
        experience = min(experience, HARD_THRESHOLD_CAP)
        keyword = min(keyword, HARD_THRESHOLD_CAP)
        project = min(project, HARD_THRESHOLD_CAP)
        education = min(education, HARD_THRESHOLD_CAP)

    overall = clamp_score(calc_overall_score(skill, experience, project, keyword, education))

    scores_dict = {
        "skillMatch": skill, "experienceMatch": experience,
        "projectMatch": project, "keywordMatch": keyword,
        "educationMatch": education
    }
    confidence = calc_confidence(
        text_quality=text_quality,
        resume_char_count=resume_char_count,
        was_split=was_split,
        llm_model=MODEL,
        scores=scores_dict,
        threshold_passed=threshold_passed,
        llm_threshold_match=llm_threshold_match,
    )
    band = get_score_band(overall)

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
        'analysis': result.get('analysis', ''),
        'confidence': confidence,
        'scoringVersion': SCORING_VERSION,
        'thresholdPassed': threshold_passed,
        'band': band['label'],
    }


# ── Keyword matching ──────────────────────────────────────────────────

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


def _calc_keyword_score(keywords: List[str],
                        resume_text: str) -> Tuple[float, List[str], List[str]]:
    """Simple text-based keyword match ratio. Returns (score_0_100, matched, missing)."""
    if not keywords:
        return 100.0, [], []

    resume_lower = resume_text.lower()
    matched = []
    missing = []

    for kw in keywords:
        kw_lower = kw.lower()
        kw_words = kw_lower.split()
        if len(kw_words) > 1:
            is_match = all(w in resume_lower for w in kw_words)
        elif _contains_cjk(kw):
            is_match = kw_lower in resume_lower
        else:
            is_match = bool(re.search(r'\b' + re.escape(kw_lower) + r'\b', resume_lower))

        if is_match:
            matched.append(kw)
        else:
            missing.append(kw)

    score = (len(matched) / len(keywords)) * 100 if keywords else 100.0
    return score, matched, missing


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


# ── Prompt templates (weight/band placeholders filled at call time) ───

PARSE_SYSTEM_MSG = """简历信息提取器，summary内容尽量完善且不超350字，简历中未提到相关内容时，填空。只输出JSON，不输出其他内容。
示例：李明，8年Java经验，精通Spring Boot、MySQL。本科，liming@example.com，13912345678。
输出：{"name":"李明","email":"liming@example.com","phone":"13912345678","skills":["Java","Spring Boot","MySQL"],"experience":8,"education":"本科","summary":"8年Java经验的工程师，精通Spring Boot、MySQL，硕士学历。"}"""

PARSE_PROMPT_TEMPLATE = """按示例格式提取。experience为纯数字，今天是{current_date}。

{resume_text}"""

MATCH_SYSTEM_MSG = """你是资深招聘匹配评估专家。严格按评分规则客观评估，确保分数有区分度。

评分维度与权重：
{dimensions_desc}

{bands_desc}

硬性门槛规则：
1. 逐条检查【必须满足】项，任意一项不满足 → 所有维度分数≤{threshold_cap}
2. 只有全部【必须满足】项都满足时，才按权重正常评分

keywordMatches/missingKeywords规则：
- keywordMatches：简历语义满足的JD关键词（含近义词如K8s=Kubernetes）
- missingKeywords：简历明确不满足的JD关键词

strengths：列出2-4个核心优势（结合JD要求）
weaknesses：列出1-3个主要不足（需具体、有依据）
analysis：综合评价，包含匹配核心理由、关键差距、发展建议，不超350字

{anchors}

注：今天是{current_date}
只输出JSON，不输出其他内容。"""

MATCH_PROMPT_TEMPLATE = """严格按评分维度评估候选人与岗位的匹配度，确保分数体现真实差距。

【候选人简历】
{resume_text}

【职位描述】
{jd_description}

{scoring_criteria}

【JD关键词】
{keywords}

{threshold_context}

【执行步骤】
步骤1 — 阅读JD：理解岗位核心要求和业务场景
步骤2 — 提取简历关键信息：技能、项目经验、教育背景、工作年限
步骤3 — 检查硬性门槛：逐条检查【必须满足】项，在简历中找到对应证据
步骤4 — 判断结果：
  - 若任意【必须满足】项在简历中明确不满足 → 所有维度分数≤{threshold_cap}
  - 若全部满足 → 按各维度的实际水平在0-100内评分
步骤5 — 填写keywordMatches/missingKeywords：keywordMatches填语义满足的（含近义词），missingKeywords填不满足的
步骤6 — 写analysis：包含硬性门槛检查结论、技能匹配度、经验适配度、发展潜力

【评分参考】
{weights_desc}

分数要有区分度：优秀≥80分，中等61-79分，不足≤40分
避免集中在70-85区间"""

# ── Threshold check prompt ────────────────────────────────────────────

THRESHOLD_SYSTEM_MSG = """你是招聘需求硬性门槛检查器。严格逐条检查简历是否满足硬性要求，给出明确证据。只输出JSON。"""

THRESHOLD_PROMPT_TEMPLATE = """逐条检查以下【必须满足】项，在简历中寻找对应证据。

【候选人简历】
{resume_text}

【职位描述】
{jd_description}

【必须满足项】
{criteria_list}

对每一项输出是否通过及证据。所有项必须全部通过才视为门槛通过。

输出格式：
{{"checks": [{{"criterion": "项目名称", "passed": true/false, "evidence": "简历中的证据或缺失说明"}}], "allPassed": true/false}}"""

# ── Merge prompts ─────────────────────────────────────────────────────

MERGE_PARSE_SYSTEM_MSG = """简历信息合并器，summary内容尽量完善且不超350字。只输出JSON，不输出其他内容。
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
  - 存在合格分后才按权重重算：{weights_formula}，四舍五入取整
- keywordMatches取并集去重
- missingKeywords只保留两份都缺失的
- strengths取并集去重，保留最多4条
- weaknesses取并集去重，保留最多3条
- analysis合并为更完整的评价
注：今天是{current_date}

结果1：{first}
结果2：{second}"""


# ── Prompt builders (shared by sync/async) ────────────────────────────

def _build_parse_messages(resume_text: str) -> list:
    prompt = PARSE_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        current_date=datetime.datetime.now().date()
    )
    return [
        {"role": "system", "content": PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]


def _parse_parse_result(result_text: str) -> Dict[str, Any]:
    result = _safe_json_parse(_clean_json_response(result_text), "parse")
    return {
        'name': result.get('name', '未知'),
        'email': result.get('email', ''),
        'phone': result.get('phone', ''),
        'skills': result.get('skills', []),
        'experience': _safe_int(result.get('experience'), 0),
        'education': result.get('education', ''),
        'summary': result.get('summary', '')
    }


def _build_threshold_messages(resume_text: str, jd_description: str,
                              must_have_items: list) -> list:
    criteria_list = '\n'.join(f"- {item}" for item in must_have_items)
    prompt = THRESHOLD_PROMPT_TEMPLATE.format(
        resume_text=resume_text[:8000],  # truncate for threshold check
        jd_description=jd_description[:4000],
        criteria_list=criteria_list
    )
    return [
        {"role": "system", "content": THRESHOLD_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]


def _parse_threshold_result(result_text: str) -> Dict[str, Any]:
    result = _safe_json_parse(_clean_json_response(result_text), "threshold")
    return {
        'checks': result.get('checks', []),
        'allPassed': result.get('allPassed', True)
    }


def _build_match_messages(resume_text: str, jd_description: str, keywords: list,
                          scoring_criteria: list = None,
                          threshold_result: Optional[Dict[str, Any]] = None) -> list:
    today = datetime.datetime.now().date()

    # Build threshold context
    if threshold_result is not None:
        if threshold_result.get('allPassed'):
            threshold_context = "【硬性门槛检查结果】✅ 已通过，全部必须满足项均已满足"
        else:
            failed_items = [c['criterion'] for c in threshold_result.get('checks', []) if not c['passed']]
            threshold_context = f"【硬性门槛检查结果】❌ 未通过，以下必须满足项未达标: {', '.join(failed_items)}。所有维度分数限制在{HARD_THRESHOLD_CAP}以内。"
    else:
        threshold_context = ""

    system_msg = MATCH_SYSTEM_MSG.format(
        dimensions_desc=format_dimensions_for_prompt(),
        bands_desc=format_bands_for_prompt(),
        anchors=format_anchors_for_prompt(),
        threshold_cap=HARD_THRESHOLD_CAP,
        current_date=today
    )
    prompt = MATCH_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        jd_description=jd_description,
        scoring_criteria=_format_scoring_criteria(scoring_criteria or []),
        keywords=','.join(keywords) if keywords else '无',
        threshold_context=threshold_context,
        threshold_cap=HARD_THRESHOLD_CAP,
        weights_desc=format_weights_for_prompt()
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]


def _parse_match_result(result_text: str, keywords: list, resume_text: str,
                        scoring_criteria: list = None,
                        must_have_failed: bool = False,
                        text_quality: float = 1.0,
                        was_split: bool = False,
                        threshold_passed: Optional[bool] = None,
                        llm_threshold_match: Optional[bool] = None) -> Dict[str, Any]:
    """Parse LLM match result, merge keywords, apply threshold cap, compute confidence."""
    result = _safe_json_parse(_clean_json_response(result_text), "match")

    # Text-based keyword matching
    text_matched, text_missing = _match_keywords(keywords, resume_text)
    llm_matched = result.get('keywordMatches', [])
    llm_missing = result.get('missingKeywords', [])
    merged_matched, merged_missing = _merge_keyword_results(
        text_matched, text_missing, llm_matched, llm_missing, keywords
    )
    result['keywordMatches'] = merged_matched
    result['missingKeywords'] = merged_missing

    # Text keyword ratio as the primary score (LLM keyword assessment is
    # already captured via keywordMatches/missingKeywords merge above)
    text_kw_score, _, _ = _calc_keyword_score(keywords, resume_text)
    result['keywordMatch'] = round(text_kw_score)

    # Detect LLM threshold judgment
    llm_all_low = all(
        _safe_float(result.get(k), 100) <= HARD_THRESHOLD_CAP
        for k in ['skillMatch', 'experienceMatch', 'projectMatch', 'keywordMatch', 'educationMatch']
    )

    return _normalize_match_result(
        result,
        must_have_failed=must_have_failed,
        text_quality=text_quality,
        resume_char_count=len(resume_text),
        was_split=was_split,
        threshold_passed=threshold_passed,
        llm_threshold_match=llm_all_low if must_have_failed else (not llm_all_low),
    )


def _build_merge_parse_messages(first: Dict[str, Any], second: Dict[str, Any]) -> list:
    prompt = MERGE_PARSE_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False)
    )
    return [
        {"role": "system", "content": MERGE_PARSE_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]


def _parse_merge_parse_result(result_text: str, first: Dict[str, Any]) -> Dict[str, Any]:
    result = _safe_json_parse(_clean_json_response(result_text), "merge_parse")
    return {
        'name': result.get('name', first.get('name', '未知')),
        'email': result.get('email', first.get('email', '')),
        'phone': result.get('phone', first.get('phone', '')),
        'skills': result.get('skills', first.get('skills', [])),
        'experience': _safe_int(result.get('experience'), first.get('experience', 0)),
        'education': result.get('education', first.get('education', '')),
        'summary': result.get('summary', first.get('summary', ''))
    }


def _build_merge_match_messages(first: Dict[str, Any], second: Dict[str, Any]) -> list:
    weights_formula = " + ".join(
        f"{key}×{info['weight']}" for key, info in DIMENSIONS.items()
    )
    today = datetime.datetime.now().date()
    prompt = MERGE_MATCH_PROMPT_TEMPLATE.format(
        first=json.dumps(first, ensure_ascii=False),
        second=json.dumps(second, ensure_ascii=False),
        weights_formula=weights_formula,
        current_date=today
    )
    return [
        {"role": "system", "content": MERGE_MATCH_SYSTEM_MSG},
        {"role": "user", "content": prompt}
    ]


# ── LLM call functions (thin IO wrappers) ─────────────────────────────

def _call_llm_parse(resume_text: str) -> Dict[str, Any]:
    messages = _build_parse_messages(resume_text)
    result_text = _chat_completion(
        messages,
        format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None
    )
    return _parse_parse_result(result_text)


async def _async_call_llm_parse(resume_text: str) -> Dict[str, Any]:
    messages = _build_parse_messages(resume_text)
    result_text = await _async_chat_completion(
        messages,
        format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None
    )
    return _parse_parse_result(result_text)


def _call_llm_threshold(resume_text: str, jd_description: str,
                        must_have_items: list) -> Dict[str, Any]:
    messages = _build_threshold_messages(resume_text, jd_description, must_have_items)
    result_text = _chat_completion(
        messages,
        format=THRESHOLD_JSON_SCHEMA if LLM_JSON_MODE else None
    )
    return _parse_threshold_result(result_text)


async def _async_call_llm_threshold(resume_text: str, jd_description: str,
                                    must_have_items: list) -> Dict[str, Any]:
    messages = _build_threshold_messages(resume_text, jd_description, must_have_items)
    result_text = await _async_chat_completion(
        messages,
        format=THRESHOLD_JSON_SCHEMA if LLM_JSON_MODE else None
    )
    return _parse_threshold_result(result_text)


def _call_llm_match(resume_text: str, jd_description: str, keywords: list,
                    scoring_criteria: list = None,
                    threshold_result: Optional[Dict[str, Any]] = None,
                    text_quality: float = 1.0) -> Dict[str, Any]:
    messages = _build_match_messages(
        resume_text, jd_description, keywords, scoring_criteria, threshold_result
    )
    logger.debug("评分提示词：")
    logger.debug(messages[-1]['content'] if messages else "")
    result_text = _chat_completion(
        messages,
        format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None,
        think=LLM_THINK_MODE
    )
    must_have_failed = (threshold_result is not None and not threshold_result.get('allPassed', True))
    return _parse_match_result(
        result_text, keywords, resume_text, scoring_criteria,
        must_have_failed=must_have_failed,
        text_quality=text_quality,
        was_split=False,
        threshold_passed=not must_have_failed if threshold_result else None,
    )


async def _async_call_llm_match(resume_text: str, jd_description: str, keywords: list,
                                scoring_criteria: list = None,
                                threshold_result: Optional[Dict[str, Any]] = None,
                                text_quality: float = 1.0) -> Dict[str, Any]:
    messages = _build_match_messages(
        resume_text, jd_description, keywords, scoring_criteria, threshold_result
    )
    logger.debug("评分提示词：")
    for message in messages:
        logger.debug("role: %s", message['role'])
        logger.debug("content: %s", message['content'])
        logger.debug("-" * 80)
    result_text = await _async_chat_completion(
        messages,
        format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None,
        think=LLM_THINK_MODE
    )
    must_have_failed = (threshold_result is not None and not threshold_result.get('allPassed', True))
    return _parse_match_result(
        result_text, keywords, resume_text, scoring_criteria,
        must_have_failed=must_have_failed,
        text_quality=text_quality,
        was_split=False,
        threshold_passed=not must_have_failed if threshold_result else None,
    )


def _llm_merge_parse(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    messages = _build_merge_parse_messages(first, second)
    result_text = _chat_completion(
        messages,
        format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None
    )
    return _parse_merge_parse_result(result_text, first)


async def _async_llm_merge_parse(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    messages = _build_merge_parse_messages(first, second)
    result_text = await _async_chat_completion(
        messages,
        format=PARSE_JSON_SCHEMA if LLM_JSON_MODE else None
    )
    return _parse_merge_parse_result(result_text, first)


def _llm_merge_match(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    messages = _build_merge_match_messages(first, second)
    result_text = _chat_completion(
        messages,
        format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None,
        think=LLM_THINK_MODE
    )
    result = _safe_json_parse(_clean_json_response(result_text), "merge_match")
    merged_matched, merged_missing = _merge_split_keyword_results(first, second)
    result['keywordMatches'] = merged_matched
    result['missingKeywords'] = merged_missing
    return _normalize_match_result(result, was_split=True)


async def _async_llm_merge_match(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    messages = _build_merge_match_messages(first, second)
    result_text = await _async_chat_completion(
        messages,
        format=MATCH_JSON_SCHEMA if LLM_JSON_MODE else None,
        think=LLM_THINK_MODE
    )
    result = _safe_json_parse(_clean_json_response(result_text), "merge_match")
    merged_matched, merged_missing = _merge_split_keyword_results(first, second)
    result['keywordMatches'] = merged_matched
    result['missingKeywords'] = merged_missing
    return _normalize_match_result(result, was_split=True)


# ── Public API ────────────────────────────────────────────────────────

def parse_resume_with_llm(resume_text: str) -> Dict[str, Any]:
    try:
        if not _should_split(len(resume_text), MAX_PARSE_CHARS):
            return _call_llm_parse(resume_text)

        first_half, second_half = _split_resume(resume_text)
        first_result = _call_llm_parse(first_half)
        second_result = _call_llm_parse(second_half)
        return _llm_merge_parse(first_result, second_result)
    except Exception as e:
        logger.error("LLM解析错误: %s", e)
        raise RuntimeError(f"简历解析失败: {e}")


def match_resume_with_jd(resume_text: str, jd_description: str, keywords: list,
                         scoring_criteria: list = None,
                         text_quality: float = 1.0) -> Dict[str, Any]:
    try:
        must_have_items = _get_must_have_criteria(scoring_criteria)
        threshold_result = None

        if must_have_items:
            threshold_result = _call_llm_threshold(
                resume_text, jd_description, must_have_items
            )

        if not _should_split(len(resume_text), MAX_MATCH_CHARS):
            return _call_llm_match(
                resume_text, jd_description, keywords, scoring_criteria,
                threshold_result=threshold_result,
                text_quality=text_quality
            )

        first_half, second_half = _split_resume(resume_text)
        first_result = _call_llm_match(
            first_half, jd_description, keywords, scoring_criteria,
            threshold_result=threshold_result,
            text_quality=text_quality
        )
        second_result = _call_llm_match(
            second_half, jd_description, keywords, scoring_criteria,
            threshold_result=threshold_result,
            text_quality=text_quality
        )
        return _llm_merge_match(first_result, second_result)
    except Exception as e:
        logger.error("LLM匹配错误: %s", e)
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
        logger.error("LLM异步解析错误: %s", e)
        raise RuntimeError(f"简历解析失败: {e}")


async def async_match_resume_with_jd(resume_text: str, jd_description: str, keywords: list,
                                     scoring_criteria: list = None,
                                     text_quality: float = 1.0) -> Dict[str, Any]:
    try:
        must_have_items = _get_must_have_criteria(scoring_criteria)
        threshold_result = None

        if must_have_items:
            threshold_result = await _async_call_llm_threshold(
                resume_text, jd_description, must_have_items
            )

        if not _should_split(len(resume_text), MAX_MATCH_CHARS):
            return await _async_call_llm_match(
                resume_text, jd_description, keywords, scoring_criteria,
                threshold_result=threshold_result,
                text_quality=text_quality
            )

        first_half, second_half = _split_resume(resume_text)
        first_result, second_result = await asyncio.gather(
            _async_call_llm_match(
                first_half, jd_description, keywords, scoring_criteria,
                threshold_result=threshold_result,
                text_quality=text_quality
            ),
            _async_call_llm_match(
                second_half, jd_description, keywords, scoring_criteria,
                threshold_result=threshold_result,
                text_quality=text_quality
            )
        )
        return await _async_llm_merge_match(first_result, second_result)
    except Exception as e:
        logger.error("LLM异步匹配错误: %s", e)
        raise RuntimeError(f"简历匹配失败: {e}")
