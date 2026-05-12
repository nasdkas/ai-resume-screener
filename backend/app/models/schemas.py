
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ResumeBase(BaseModel):
    filename: str
    originalFilename: Optional[str] = None
    name: str
    email: str
    phone: str
    skills: List[str]
    experience: int
    education: str
    summary: str
    rawText: str
    keywordMatches: List[str] = []
    missingKeywords: List[str] = []
    parseStatus: str = "parsing"
    matchStatus: Optional[str] = None
    jdId: Optional[str] = None


class ResumeCreate(ResumeBase):
    pass


class Resume(ResumeBase):
    id: str
    createdAt: datetime

    class Config:
        from_attributes = True


class ScoringCriterion(BaseModel):
    item: str
    weight: str = "必须"


class JDBase(BaseModel):
    title: str
    description: str
    keywords: List[str]
    scoringCriteria: List[ScoringCriterion] = []


class JDCreate(JDBase):
    pass


class JDUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    scoringCriteria: Optional[List[ScoringCriterion]] = None


class JD(JDBase):
    id: str
    createdAt: datetime

    class Config:
        from_attributes = True


class MatchResultBase(BaseModel):
    resumeId: str
    jdId: str
    overallScore: float
    skillMatch: float
    experienceMatch: float
    educationMatch: float
    keywordMatch: float = 0
    projectMatch: float = 0
    keywordMatches: List[str]
    missingKeywords: List[str]
    strengths: List[str] = []
    weaknesses: List[str] = []
    analysis: str


class MatchResultCreate(MatchResultBase):
    pass


class MatchResult(MatchResultBase):
    id: str
    createdAt: datetime

    class Config:
        from_attributes = True


class MatchRequest(BaseModel):
    jdId: str
    resumeIds: Optional[List[str]] = None


class MatchResponse(BaseModel):
    success: bool
    results: List[MatchResult]


class UploadResponse(BaseModel):
    success: bool
    resume: Resume


class UploadResult(BaseModel):
    filename: str
    success: bool
    resume: Optional[Resume] = None
    error: Optional[str] = None


class BatchUploadResponse(BaseModel):
    results: List[UploadResult]


class FailedUpload(BaseModel):
    id: str
    filename: str
    error: str
    createdAt: datetime

    class Config:
        from_attributes = True
