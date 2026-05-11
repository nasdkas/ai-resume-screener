
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from typing import List, Optional
from datetime import datetime
import asyncio

from app.models.schemas import (
    Resume, JD, MatchResult, MatchRequest, MatchResponse, UploadResponse,
    UploadResult, BatchUploadResponse, JDCreate, JDUpdate, FailedUpload
)
from app.services.storage import (
    save_resume, get_all_resumes, get_resume_by_id, delete_resume,
    update_resume,
    save_jd, get_all_jds, get_jd_by_id, update_jd, delete_jd,
    get_match_results_by_jd_id, get_all_match_results,
    get_match_result_by_resume_and_jd,
    save_failed_upload, get_all_failed_uploads, delete_failed_upload,
    delete_failed_uploads_by_filename
)
from app.services.parser import extract_text
from app.services.llm_service import async_parse_resume_with_llm
from app.services.matcher import async_match_all_resumes, async_match_single_resume

router = APIRouter(prefix="/api", tags=["api"])


def _to_resume(resume: dict) -> Resume:
    return Resume(
        id=resume['id'],
        filename=resume['filename'],
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
        createdAt=datetime.fromisoformat(r['createdAt'])
    )


async def _parse_resume_background(resume_id: str, raw_text: str, filename: str, jd_id: str = None):
    try:
        parsed_data = await async_parse_resume_with_llm(raw_text)
        update_resume(resume_id, {
            **parsed_data,
            'parseStatus': 'completed'
        })
        delete_failed_uploads_by_filename(filename)
        if jd_id:
            try:
                await async_match_single_resume(resume_id, jd_id)
            except Exception as e:
                print(f"自动匹配失败: {e}")
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
        await asyncio.gather(*batch, return_exceptions=True)


@router.post("/upload", response_model=UploadResponse)
async def upload_resume(file: UploadFile = File(...), jdId: Optional[str] = Form(None), background_tasks: BackgroundTasks = None):
    file_bytes = await file.read()
    raw_text = extract_text(file_bytes, file.filename)

    if not raw_text:
        save_failed_upload(file.filename or "未知文件", "不支持的文件格式")
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    resume_data = {
        'filename': file.filename or "未知文件",
        'rawText': raw_text,
        'name': '解析中...',
        'email': '',
        'phone': '',
        'skills': [],
        'experience': 0,
        'education': '',
        'summary': '',
        'parseStatus': 'parsing',
        'jdId': jdId
    }

    resume = save_resume(resume_data)
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

            resume_data = {
                'filename': file.filename or "未知文件",
                'rawText': raw_text,
                'name': '解析中...',
                'email': '',
                'phone': '',
                'skills': [],
                'experience': 0,
                'education': '',
                'summary': '',
                'parseStatus': 'parsing',
                'jdId': jdId
            }

            resume = save_resume(resume_data)
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


@router.get("/resumes", response_model=List[Resume])
async def list_resumes():
    resumes = get_all_resumes()
    return [_to_resume(r) for r in resumes]


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
    return {"success": True}


@router.post("/jds", response_model=JD)
async def create_jd(jd_data: JDCreate):
    jd = save_jd(jd_data.model_dump())
    return _to_jd(jd)


@router.get("/jds", response_model=List[JD])
async def list_jds():
    jds = get_all_jds()
    return [_to_jd(j) for j in jds]


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
