import asyncio
from typing import List, Dict, Any, Optional
from .storage import get_jd_by_id, get_resume_by_id, get_all_resumes, save_match_result, get_match_result_by_resume_and_jd, delete_match_result
from .llm_service import match_resume_with_jd, async_match_resume_with_jd

BATCH_SIZE = 3


def match_single_resume(resume_id: str, jd_id: str) -> Dict[str, Any]:
    resume = get_resume_by_id(resume_id)
    jd = get_jd_by_id(jd_id)

    if not resume or not jd:
        raise ValueError("Resume or JD not found")

    if resume.get('parseStatus', 'completed') != 'completed':
        raise ValueError("简历尚未解析完成，无法匹配")

    match_result = match_resume_with_jd(
        resume['rawText'],
        jd['description'],
        jd['keywords'],
        jd.get('scoringCriteria', [])
    )

    result_data = {
        'resumeId': resume_id,
        'jdId': jd_id,
        **match_result
    }

    return save_match_result(result_data)


def rematch_single_resume(resume_id: str, jd_id: str) -> Dict[str, Any]:
    resume = get_resume_by_id(resume_id)
    jd = get_jd_by_id(jd_id)

    if not resume or not jd:
        raise ValueError("Resume or JD not found")

    if resume.get('parseStatus', 'completed') != 'completed':
        raise ValueError("简历尚未解析完成，无法匹配")

    delete_match_result(resume_id, jd_id)

    match_result = match_resume_with_jd(
        resume['rawText'],
        jd['description'],
        jd['keywords'],
        jd.get('scoringCriteria', [])
    )

    result_data = {
        'resumeId': resume_id,
        'jdId': jd_id,
        **match_result
    }

    return save_match_result(result_data)


async def async_rematch_single_resume(resume_id: str, jd_id: str) -> Dict[str, Any]:
    resume = get_resume_by_id(resume_id)
    jd = get_jd_by_id(jd_id)

    if not resume or not jd:
        raise ValueError("Resume or JD not found")

    if resume.get('parseStatus', 'completed') != 'completed':
        raise ValueError("简历尚未解析完成，无法匹配")

    delete_match_result(resume_id, jd_id)

    match_result = await async_match_resume_with_jd(
        resume['rawText'],
        jd['description'],
        jd['keywords'],
        jd.get('scoringCriteria', [])
    )

    result_data = {
        'resumeId': resume_id,
        'jdId': jd_id,
        **match_result
    }

    return save_match_result(result_data)


def match_all_resumes(jd_id: str, resume_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    jd = get_jd_by_id(jd_id)
    if not jd:
        raise ValueError("JD not found")

    resumes = get_all_resumes()
    if resume_ids:
        resumes = [r for r in resumes if r['id'] in resume_ids]
    resumes = [r for r in resumes if r.get('parseStatus', 'completed') == 'completed']
    resumes = [r for r in resumes if not r.get('jdId') or r['jdId'] == jd_id]

    existing_results = []
    new_resumes = []
    for resume in resumes:
        existing = get_match_result_by_resume_and_jd(resume['id'], jd_id)
        if existing:
            existing_results.append(existing)
        else:
            new_resumes.append(resume)

    for resume in new_resumes:
        try:
            match_result = match_resume_with_jd(
                resume['rawText'],
                jd['description'],
                jd['keywords'],
                jd.get('scoringCriteria', [])
            )

            result_data = {
                'resumeId': resume['id'],
                'jdId': jd_id,
                **match_result
            }

            saved_result = save_match_result(result_data)
            existing_results.append(saved_result)
        except Exception as e:
            print(f"匹配简历 {resume['id']} 失败: {e}")

    existing_results.sort(key=lambda x: x['overallScore'], reverse=True)
    return existing_results


async def _match_one_resume(resume: dict, jd_id: str, jd_description: str, jd_keywords: list, jd_scoring_criteria: list) -> Optional[Dict[str, Any]]:
    try:
        match_result = await async_match_resume_with_jd(
            resume['rawText'],
            jd_description,
            jd_keywords,
            jd_scoring_criteria
        )
        result_data = {
            'resumeId': resume['id'],
            'jdId': jd_id,
            **match_result
        }
        return save_match_result(result_data)
    except Exception as e:
        print(f"匹配简历 {resume['id']} 失败: {e}")
        return None


async def async_match_all_resumes(jd_id: str, resume_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    jd = get_jd_by_id(jd_id)
    if not jd:
        raise ValueError("JD not found")

    resumes = get_all_resumes()
    if resume_ids:
        resumes = [r for r in resumes if r['id'] in resume_ids]
    resumes = [r for r in resumes if r.get('parseStatus', 'completed') == 'completed']
    resumes = [r for r in resumes if not r.get('jdId') or r['jdId'] == jd_id]

    existing_results = []
    new_resumes = []
    for resume in resumes:
        existing = get_match_result_by_resume_and_jd(resume['id'], jd_id)
        if existing:
            existing_results.append(existing)
        else:
            new_resumes.append(resume)

    if new_resumes:
        tasks = [
            _match_one_resume(resume, jd_id, jd['description'], jd['keywords'], jd.get('scoringCriteria', []))
            for resume in new_resumes
        ]
        for i in range(0, len(tasks), BATCH_SIZE):
            batch = tasks[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(*batch)
            for result in batch_results:
                if result:
                    existing_results.append(result)

    existing_results.sort(key=lambda x: x['overallScore'], reverse=True)
    return existing_results
