
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

from app.models.schemas import (
    Resume, JD, MatchResult, MatchRequest, MatchResponse, UploadResponse,
    UploadResult, BatchUploadResponse, JDCreate, JDUpdate, FailedUpload,
    PaginatedResumes, PaginatedJDs, ResumeUpdate
)
from app.services.storage import (
    save_resume, get_all_resumes, get_all_resumes_paginated, get_resume_by_id, delete_resume,
    update_resume,
    save_jd, get_all_jds, get_all_jds_paginated, get_jd_by_id, update_jd, delete_jd,
    get_match_results_by_jd_id, get_all_match_results,
    get_match_result_by_resume_and_jd,
    save_failed_upload, get_all_failed_uploads, delete_failed_upload,
    delete_failed_uploads_by_filename
)
from app.services.parser import extract_text, calc_text_quality
from app.services.llm_service import async_parse_resume_with_llm
from app.services.matcher import async_match_all_resumes, async_match_single_resume, get_match_progress
from app.services.file_storage import save_resume_file, get_resume_file_info, delete_resume_file

router = APIRouter(prefix="/api", tags=["api"])


def _to_resume(resume: dict) -> Resume:
    return Resume(
        id=resume['id'],
        filename=resume['filename'],
        originalFilename=resume.get('originalFilename'),
        name=resume['name'],
        email=resume['email'],
        phone=resume['phone'],
        skills=resume['skills'],
        experience=resume['experience'],
        education=resume['education'],
        summary=resume['summary'],
        rawText=resume['rawText'],
        keywordMatches=resume.get('keywordMatches', []),
        missingKeywords=resume.get('missingKeywords', []),
        parseStatus=resume.get('parseStatus', 'completed'),
        matchStatus=resume.get('matchStatus'),
        jdId=resume.get('jdId'),
        createdAt=datetime.fromisoformat(resume['createdAt'])
    )


def _to_jd(jd: dict) -> JD:
    return JD(
        id=jd['id'],
        title=jd['title'],
        description=jd['description'],
        keywords=jd['keywords'],
        scoringCriteria=jd.get('scoringCriteria', []),
        createdAt=datetime.fromisoformat(jd['createdAt'])
    )


def _to_match_result(r: dict) -> MatchResult:
    return MatchResult(
        id=r['id'],
        resumeId=r['resumeId'],
        jdId=r['jdId'],
        overallScore=r['overallScore'],
        skillMatch=r['skillMatch'],
        experienceMatch=r['experienceMatch'],
        educationMatch=r['educationMatch'],
        keywordMatch=r.get('keywordMatch', 0),
        projectMatch=r.get('projectMatch', 0),
        keywordMatches=r['keywordMatches'],
        missingKeywords=r['missingKeywords'],
        strengths=r.get('strengths', []),
        weaknesses=r.get('weaknesses', []),
        analysis=r['analysis'],
        confidence=r.get('confidence'),
        scoringVersion=r.get('scoringVersion'),
        thresholdPassed=r.get('thresholdPassed'),
        band=r.get('band'),
        createdAt=datetime.fromisoformat(r['createdAt'])
    )


async def _parse_resume_background(resume_id: str, raw_text: str, filename: str, jd_id: str = None):
    try:
        parsed_data = await async_parse_resume_with_llm(raw_text)
        update_resume(resume_id, {
            **parsed_data,
            'parseStatus': 'completed',
            'matchStatus': 'matching' if jd_id else None
        })
        delete_failed_uploads_by_filename(filename)
        if jd_id:
            try:
                await async_match_single_resume(resume_id, jd_id)
                update_resume(resume_id, {'matchStatus': 'completed'})
            except Exception as e:
                logger.warning("自动匹配失败: %s", e)
                update_resume(resume_id, {'matchStatus': 'failed'})
    except Exception as e:
        error_msg = f"解析失败: {str(e)}"
        save_failed_upload(filename, error_msg)
        update_resume(resume_id, {
            'parseStatus': 'failed',
            'parseError': error_msg
        })


BATCH_SIZE = 2


async def _parse_resumes_batch_background(tasks: list):
    for i in range(0, len(tasks), BATCH_SIZE):
        batch = tasks[i:i + BATCH_SIZE]
        results = await asyncio.gather(*batch, return_exceptions=True)
        for j, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning("批量任务 %d 执行异常: %s", i + j, r)


@router.post("/upload", response_model=UploadResponse)
async def upload_resume(file: UploadFile = File(...), jdId: Optional[str] = Form(None), background_tasks: BackgroundTasks = None):
    file_bytes = await file.read()
    raw_text = extract_text(file_bytes, file.filename)

    if not raw_text:
        save_failed_upload(file.filename or "未知文件", "不支持的文件格式")
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    text_quality = calc_text_quality(raw_text)

    resume_data = {
        'filename': file.filename or "未知文件",
        'originalFilename': file.filename or "未知文件",
        'rawText': raw_text,
        'name': '解析中...',
        'email': '',
        'phone': '',
        'skills': [],
        'experience': 0,
        'education': '',
        'summary': '',
        'parseStatus': 'parsing',
        'jdId': jdId,
        'textQuality': text_quality
    }

    resume = save_resume(resume_data)

    try:
        save_resume_file(resume['id'], file_bytes, file.filename or "未知文件")
    except Exception as e:
        delete_resume(resume['id'])
        save_failed_upload(file.filename or "未知文件", f"文件存储失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件存储失败: {str(e)}")

    background_tasks.add_task(_parse_resume_background, resume['id'], raw_text, file.filename or "未知文件", jdId)

    return UploadResponse(success=True, resume=_to_resume(resume))


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_resumes_batch(files: List[UploadFile] = File(...), jdId: Optional[str] = Form(None), background_tasks: BackgroundTasks = None):
    results = []
    parse_tasks = []
    for file in files:
        try:
            file_bytes = await file.read()
            raw_text = extract_text(file_bytes, file.filename)

            if not raw_text:
                save_failed_upload(file.filename or "未知文件", "不支持的文件格式")
                results.append(UploadResult(
                    filename=file.filename,
                    success=False,
                    error="不支持的文件格式"
                ))
                continue

            text_quality = calc_text_quality(raw_text)

            resume_data = {
                'filename': file.filename or "未知文件",
                'originalFilename': file.filename or "未知文件",
                'rawText': raw_text,
                'name': '解析中...',
                'email': '',
                'phone': '',
                'skills': [],
                'experience': 0,
                'education': '',
                'summary': '',
                'parseStatus': 'parsing',
                'jdId': jdId,
                'textQuality': text_quality
            }

            resume = save_resume(resume_data)
            try:
                save_resume_file(resume['id'], file_bytes, file.filename or "未知文件")
            except Exception:
                delete_resume(resume['id'])
                raise
            parse_tasks.append(_parse_resume_background(resume['id'], raw_text, file.filename or "未知文件", jdId))
            results.append(UploadResult(
                filename=file.filename,
                success=True,
                resume=_to_resume(resume)
            ))
        except Exception as e:
            error_msg = f"上传失败: {str(e)}"
            save_failed_upload(file.filename or "未知文件", error_msg)
            results.append(UploadResult(
                filename=file.filename,
                success=False,
                error=error_msg
            ))

    if parse_tasks:
        background_tasks.add_task(_parse_resumes_batch_background, parse_tasks)

    return BatchUploadResponse(results=results)


@router.get("/resumes", response_model=PaginatedResumes)
async def list_resumes(page: int = 1, page_size: int = 10, jd_id: Optional[str] = None):
    page_size = max(1, min(page_size, 100))
    page = max(1, page)
    items, total = get_all_resumes_paginated(page, page_size, jd_id)
    return PaginatedResumes(
        items=[_to_resume(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=-(-total // page_size)
    )


@router.get("/resumes/{resume_id}", response_model=Resume)
async def get_resume(resume_id: str):
    resume = get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return _to_resume(resume)


@router.delete("/resumes/{resume_id}")
async def delete_resume_endpoint(resume_id: str):
    success = delete_resume(resume_id)
    if not success:
        raise HTTPException(status_code=404, detail="Resume not found")
    delete_resume_file(resume_id)
    return {"success": True}


@router.put("/resumes/{resume_id}", response_model=Resume)
async def update_resume_endpoint(resume_id: str, resume_data: ResumeUpdate):
    resume = get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    updates = {k: v for k, v in resume_data.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = update_resume(resume_id, updates)
    return _to_resume(updated)


@router.get("/resumes/{resume_id}/file")
async def get_resume_file(resume_id: str):
    resume = get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    file_info = get_resume_file_info(resume_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Resume file not found")
    
    file_path, mime_type = file_info
    
    return FileResponse(
        path=file_path,
        media_type=mime_type
    )


@router.post("/jds", response_model=JD)
async def create_jd(jd_data: JDCreate):
    jd = save_jd(jd_data.model_dump())
    return _to_jd(jd)


@router.get("/jds", response_model=PaginatedJDs)
async def list_jds(page: int = 1, page_size: int = 50):
    page_size = max(1, min(page_size, 200))
    page = max(1, page)
    items, total = get_all_jds_paginated(page, page_size)
    return PaginatedJDs(
        items=[_to_jd(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=-(-total // page_size)
    )


@router.get("/jds/{jd_id}", response_model=JD)
async def get_jd_endpoint(jd_id: str):
    jd = get_jd_by_id(jd_id)
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return _to_jd(jd)


@router.put("/jds/{jd_id}", response_model=JD)
async def update_jd_endpoint(jd_id: str, jd_data: JDUpdate):
    updates = {k: v for k, v in jd_data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    jd = update_jd(jd_id, updates)
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return _to_jd(jd)


@router.delete("/jds/{jd_id}")
async def delete_jd_endpoint(jd_id: str):
    success = delete_jd(jd_id)
    if not success:
        raise HTTPException(status_code=404, detail="JD not found")
    return {"success": True}


@router.post("/match", response_model=MatchResponse)
async def match_resumes(request: MatchRequest):
    try:
        results = await async_match_all_resumes(request.jdId, request.resumeIds)
        return MatchResponse(
            success=True,
            results=[_to_match_result(r) for r in results]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/match/progress/{jd_id}")
async def get_match_progress_endpoint(jd_id: str):
    progress = get_match_progress(jd_id)
    if not progress:
        return {"total": 0, "completed": 0}
    return progress


@router.get("/matches/{jd_id}", response_model=List[MatchResult])
async def get_matches_by_jd(jd_id: str):
    results = get_match_results_by_jd_id(jd_id)
    return [_to_match_result(r) for r in results]


@router.get("/matches", response_model=List[MatchResult])
async def get_all_matches():
    results = get_all_match_results()
    return [_to_match_result(r) for r in results]


@router.get("/match/{resume_id}/{jd_id}", response_model=MatchResult)
async def get_match_result(resume_id: str, jd_id: str):
    result = get_match_result_by_resume_and_jd(resume_id, jd_id)
    if not result:
        raise HTTPException(status_code=404, detail="Match result not found")
    return _to_match_result(result)


@router.post("/match/{resume_id}/{jd_id}", response_model=MatchResult)
async def score_single_resume(resume_id: str, jd_id: str):
    try:
        result = await async_match_single_resume(resume_id, jd_id)
        return _to_match_result(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/failed-uploads", response_model=List[FailedUpload])
async def list_failed_uploads():
    records = get_all_failed_uploads()
    return [
        FailedUpload(
            id=r['id'],
            filename=r['filename'],
            error=r['error'],
            createdAt=datetime.fromisoformat(r['createdAt'])
        )
        for r in records
    ]


@router.delete("/failed-uploads/{failed_id}")
async def delete_failed_upload_endpoint(failed_id: str):
    success = delete_failed_upload(failed_id)
    if not success:
        raise HTTPException(status_code=404, detail="Failed upload not found")
    return {"success": True}


@router.post("/resumes/{resume_id}/retry", response_model=Resume)
async def retry_parse_resume(resume_id: str):
    resume = get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.get('parseStatus') != 'failed':
        raise HTTPException(status_code=400, detail="Resume is not in failed status")

    raw_text = resume.get('rawText', '')
    if not raw_text:
        raise HTTPException(status_code=400, detail="No raw text available for retry")

    try:
        parsed_data = await async_parse_resume_with_llm(raw_text)
        updated = update_resume(resume_id, {
            **parsed_data,
            'parseStatus': 'completed',
            'parseError': None,
            'matchStatus': 'matching' if resume.get('jdId') else None
        })
        delete_failed_uploads_by_filename(resume.get('filename', ''))
        jd_id = resume.get('jdId')
        if jd_id:
            try:
                await async_match_single_resume(resume_id, jd_id)
                update_resume(resume_id, {'matchStatus': 'completed'})
            except Exception as e:
                logger.error("重试后自动匹配失败: %s", e)
                update_resume(resume_id, {'matchStatus': 'failed'})
        return _to_resume(updated)
    except Exception as e:
        error_msg = f"重试解析失败: {str(e)}"
        update_resume(resume_id, {'parseError': error_msg})
        raise HTTPException(status_code=500, detail=error_msg)
