
export interface Resume {
  id: string;
  filename: string;
  originalFilename?: string;
  name: string;
  email: string;
  phone: string;
  skills: string[];
  experience: number;
  education: string;
  summary: string;
  rawText: string;
  keywordMatches: string[];
  missingKeywords: string[];
  parseStatus: 'parsing' | 'completed' | 'failed';
  matchStatus?: 'matching' | 'completed' | 'failed';
  jdId?: string;
  createdAt: string;
}

export interface ScoringCriterion {
  item: string;
  weight: string;
}

export interface JD {
  id: string;
  title: string;
  description: string;
  keywords: string[];
  scoringCriteria: ScoringCriterion[];
  createdAt: string;
}

export interface MatchResult {
  id: string;
  resumeId: string;
  jdId: string;
  overallScore: number;
  skillMatch: number;
  experienceMatch: number;
  educationMatch: number;
  keywordMatch: number;
  projectMatch: number;
  keywordMatches: string[];
  missingKeywords: string[];
  strengths: string[];
  weaknesses: string[];
  analysis: string;
  createdAt: string;
}

export interface UploadResult {
  filename: string;
  success: boolean;
  resume?: Resume;
  error?: string;
}

export interface BatchUploadResponse {
  results: UploadResult[];
}

export interface FailedUpload {
  id: string;
  filename: string;
  error: string;
  createdAt: string;
}

export interface MatchRequest {
  jdId: string;
  resumeIds?: string[];
}

export interface MatchResponse {
  success: boolean;
  results: MatchResult[];
}
