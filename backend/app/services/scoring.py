"""
Single source of truth for all resume scoring constants, weights, bands, and calculations.
Import from this module everywhere -- do NOT hardcode weights in prompts or UI.
"""
from typing import Dict, List, Tuple, Optional
from collections import OrderedDict
import statistics

SCORING_VERSION = "2.0"

# ── Dimensions (order matters for display) ────────────────────────────
DIMENSIONS = OrderedDict({
    "skillMatch":      {"label": "技能匹配",   "key": "skill",       "weight": 0.35},
    "experienceMatch": {"label": "经验匹配",   "key": "experience",  "weight": 0.25},
    "projectMatch":    {"label": "项目匹配",   "key": "project",     "weight": 0.20},
    "keywordMatch":    {"label": "关键词匹配", "key": "keyword",     "weight": 0.10},
    "educationMatch":  {"label": "学历匹配",   "key": "education",   "weight": 0.10},
})

# Validate weights sum to 1.0 at import time
assert abs(sum(d["weight"] for d in DIMENSIONS.values()) - 1.0) < 0.001, \
    f"Dimension weights must sum to 1.0, got {sum(d['weight'] for d in DIMENSIONS.values())}"

DIMENSION_KEYS = list(DIMENSIONS.keys())

# ── Score Bands ───────────────────────────────────────────────────────
SCORE_BANDS: List[Tuple[int, int, str]] = [
    (0,  20, "完全不匹配"),
    (21, 40, "大部分不满足"),
    (41, 60, "部分满足，有明显差距"),
    (61, 80, "基本满足，略有不足"),
    (81, 100, "完全满足或超出预期"),
]

# Display-friendly bands (3 tiers for visual)
DISPLAY_BANDS: List[Tuple[int, int, str, str]] = [
    (0,  39, "不匹配",   "red"),
    (40, 59, "部分匹配", "yellow"),
    (60, 79, "基本匹配", "yellow"),
    (80, 100, "高度匹配", "green"),
]

# ── Threshold ─────────────────────────────────────────────────────────
HARD_THRESHOLD_CAP = 40  # max score for any dimension when must-have criteria fail

# ── Calibration anchors ───────────────────────────────────────────────
CALIBRATION_ANCHORS = [
    {
        "description": "高度匹配：技能100%覆盖JD，项目经验高度对口，10年经验满足5年要求",
        "scores": {"skillMatch": 95, "experienceMatch": 90, "projectMatch": 92,
                    "keywordMatch": 90, "educationMatch": 85},
    },
    {
        "description": "基本匹配：技能70%覆盖JD，有相关但不完全对口的项目经验，经验年限略低",
        "scores": {"skillMatch": 72, "experienceMatch": 65, "projectMatch": 60,
                    "keywordMatch": 55, "educationMatch": 80},
    },
    {
        "description": "完全不匹配：JD要求Java后端/Spring Boot，候选人是销售背景",
        "scores": {"skillMatch": 10, "experienceMatch": 8, "projectMatch": 5,
                    "keywordMatch": 5, "educationMatch": 15},
    },
]

# ── Model tier confidence ─────────────────────────────────────────────
# Base confidence by model family -- used when model name matches a prefix
MODEL_CONFIDENCE_MAP: Dict[str, float] = {
    "deepseek-v4-flash":     0.92,
    "qwen3.5-plus":        0.85,
    "gemma4:26b":           0.60,
    "gemma4:e4b":           0.50,
}
DEFAULT_MODEL_CONFIDENCE = 0.70


# ── Calculation functions ─────────────────────────────────────────────

def calc_overall_score(skill: float, experience: float, project: float,
                       keyword: float, education: float) -> float:
    """Weighted overall score from 5 dimensions. The *only* place this formula lives."""
    weights = {d["key"]: d["weight"] for d in DIMENSIONS.values()}
    return round(
        skill * weights["skill"]
        + experience * weights["experience"]
        + project * weights["project"]
        + keyword * weights["keyword"]
        + education * weights["education"]
    )


def clamp_score(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def get_score_band(score: float) -> dict:
    """Return the band dict {min, max, label} for a given score."""
    for lo, hi, label in SCORE_BANDS:
        if lo <= score <= hi:
            return {"min": lo, "max": hi, "label": label}
    return {"min": 0, "max": 100, "label": "未知"}


def get_display_band(score: float) -> dict:
    """Return display-friendly band {label, color} for UI."""
    for lo, hi, label, color in DISPLAY_BANDS:
        if lo <= score <= hi:
            return {"label": label, "color": color}
    return {"label": "未知", "color": "gray"}


def calc_confidence(*, text_quality: float = 1.0, resume_char_count: int = 0,
                    was_split: bool = False, llm_model: str = "",
                    scores: Optional[Dict[str, float]] = None,
                    threshold_passed: Optional[bool] = None,
                    llm_threshold_match: Optional[bool] = None) -> float:
    """Calculate a confidence score (0.0 - 1.0) for a match result."""
    components = []

    # 1. Text quality (weight 0.25)
    components.append(("text_quality", clamp_score(text_quality, 0.0, 1.0), 0.25))

    # 2. Resume length adequacy (weight 0.10)
    length_score = min(1.0, resume_char_count / 800)
    components.append(("length", length_score, 0.10))

    # 3. Split penalty (weight 0.10)
    components.append(("split", 0.85 if was_split else 1.0, 0.10))

    # 4. Model tier (weight 0.15)
    model_score = _model_confidence(llm_model)
    components.append(("model", model_score, 0.15))

    # 5. Score variance (weight 0.25)
    variance_score = _variance_confidence(scores)
    components.append(("variance", variance_score, 0.25))

    # 6. Threshold agreement (weight 0.15)
    if threshold_passed is not None and llm_threshold_match is not None:
        threshold_score = 1.0 if threshold_passed == llm_threshold_match else 0.6
    else:
        threshold_score = 1.0  # no threshold check to compare
    components.append(("threshold", threshold_score, 0.15))

    return clamp_score(sum(s * w for _, s, w in components), 0.0, 1.0)


def _model_confidence(model_name: str) -> float:
    """Map model name to base confidence level."""
    model_lower = model_name.lower()
    for prefix, conf in MODEL_CONFIDENCE_MAP.items():
        if model_lower.startswith(prefix):
            return conf
    return DEFAULT_MODEL_CONFIDENCE


def _variance_confidence(scores: Optional[Dict[str, float]]) -> float:
    """Higher variance across dimensions -> more differentiated -> more confident."""
    if not scores:
        return 0.7
    values = [scores.get(k, 0) for k in DIMENSION_KEYS if k in scores]
    if len(values) < 3:
        return 0.7
    try:
        stdev = statistics.stdev(values)
    except statistics.StatisticsError:
        return 0.7
    # Map stdev to confidence: stdev 0-5 -> 0.4, 5-15 -> 0.7, 15-25 -> 0.9, >30 -> 1.0
    if stdev < 3:
        return 0.35
    elif stdev < 8:
        return 0.55
    elif stdev < 15:
        return 0.75
    elif stdev < 25:
        return 0.90
    else:
        return 1.0


# ── Prompt formatters ─────────────────────────────────────────────────

def format_dimensions_for_prompt() -> str:
    """Generate dimension + weight description for LLM system prompt."""
    lines = []
    for key, info in DIMENSIONS.items():
        pct = round(info["weight"] * 100)
        lines.append(f"- {key}（{info['label']}，权重{pct}%）")
    return "\n".join(lines)


def format_bands_for_prompt() -> str:
    """Generate score band descriptions for LLM system prompt."""
    lines = ["分数级别（必须使用全范围，避免集中在70-85）："]
    for lo, hi, label in SCORE_BANDS:
        lines.append(f"- {lo}-{hi}：{label}")
    return "\n".join(lines)


def format_anchors_for_prompt() -> str:
    """Generate calibration anchor examples for LLM system prompt."""
    lines = ["【校准锚点（内部参考，请据此校准你的评分尺度）】"]
    for i, anchor in enumerate(CALIBRATION_ANCHORS, 1):
        s = anchor["scores"]
        overall = calc_overall_score(
            s["skillMatch"], s["experienceMatch"], s["projectMatch"],
            s["keywordMatch"], s["educationMatch"]
        )
        score_str = ", ".join(
            f"{key}≈{s[key]}" for key in DIMENSION_KEYS
        )
        lines.append(f"案例{i} — {anchor['description']}")
        lines.append(f"  → {score_str}, overall≈{overall}")
    return "\n".join(lines)


def format_weights_for_prompt() -> str:
    """Generate concise weight reference for user prompt."""
    lines = []
    for key, info in DIMENSIONS.items():
        pct = round(info["weight"] * 100)
        lines.append(f"- {key} {pct}%：{info['label']}")
    return "\n".join(lines)
