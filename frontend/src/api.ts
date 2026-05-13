import { Resume, JD, ScoringCriterion, MatchResult, UploadResponse, BatchUploadResponse, MatchRequest, MatchResponse, FailedUpload, PaginatedResponse } from './types';
import { toast } from './lib/toast';

const API_BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errMsg = `请求失败 (${response.status})`;
    toast.error(errMsg);
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

/** Non-JSON request (e.g. file upload) with its own error handling */
async function rawRequest(url: string, options: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${url}`, options);
  if (!response.ok) {
    const errMsg = `请求失败 (${response.status})`;
    toast.error(errMsg);
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response;
}

export const api = {
  getMatchProgress: async (jdId: string): Promise<{ total: number; completed: number }> => {
    return request<{ total: number; completed: number }>(`/match/progress/${jdId}`);
  },

  uploadResume: async (file: File, jdId?: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (jdId) {
      formData.append('jdId', jdId);
    }

    const response = await rawRequest('/upload', {
      method: 'POST',
      body: formData,
    });

    return response.json();
  },

  uploadResumesBatch: async (files: File[], jdId?: string): Promise<BatchUploadResponse> => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    if (jdId) {
      formData.append('jdId', jdId);
    }

    const response = await rawRequest('/upload/batch', {
      method: 'POST',
      body: formData,
    });

    return response.json();
  },

  getResumes: async (params?: { page?: number; pageSize?: number; jdId?: string }): Promise<PaginatedResponse<Resume>> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize));
    if (params?.jdId) searchParams.set('jd_id', params.jdId);
    const qs = searchParams.toString();
    return request<PaginatedResponse<Resume>>(`/resumes${qs ? '?' + qs : ''}`);
  },

  getResume: async (id: string): Promise<Resume> => {
    return request<Resume>(`/resumes/${id}`);
  },

  deleteResume: async (id: string): Promise<{ success: boolean }> => {
    return request<{ success: boolean }>(`/resumes/${id}`, { method: 'DELETE' });
  },

  updateResume: async (id: string, data: Partial<Pick<Resume, 'name' | 'email' | 'phone' | 'skills' | 'experience' | 'education' | 'summary' | 'rawText'>>): Promise<Resume> => {
    return request<Resume>(`/resumes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  createJD: async (data: { title: string; description: string; keywords: string[]; scoringCriteria?: ScoringCriterion[] }): Promise<JD> => {
    return request<JD>('/jds', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getJDs: async (params?: { page?: number; pageSize?: number }): Promise<PaginatedResponse<JD>> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize));
    const qs = searchParams.toString();
    return request<PaginatedResponse<JD>>(`/jds${qs ? '?' + qs : ''}`);
  },

  getJD: async (id: string): Promise<JD> => {
    return request<JD>(`/jds/${id}`);
  },

  updateJD: async (id: string, data: Partial<{ title: string; description: string; keywords: string[]; scoringCriteria: ScoringCriterion[] }>): Promise<JD> => {
    return request<JD>(`/jds/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteJD: async (id: string): Promise<{ success: boolean }> => {
    return request<{ success: boolean }>(`/jds/${id}`, { method: 'DELETE' });
  },

  matchResumes: async (data: MatchRequest): Promise<MatchResponse> => {
    return request<MatchResponse>('/match', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getMatchResultsByJd: async (jdId: string): Promise<MatchResult[]> => {
    return request<MatchResult[]>(`/matches/${jdId}`);
  },

  getAllMatchResults: async (): Promise<MatchResult[]> => {
    return request<MatchResult[]>('/matches');
  },

  getMatchResult: async (resumeId: string, jdId: string): Promise<MatchResult> => {
    return request<MatchResult>(`/match/${resumeId}/${jdId}`);
  },

  scoreSingleResume: async (resumeId: string, jdId: string): Promise<MatchResult> => {
    return request<MatchResult>(`/match/${resumeId}/${jdId}`, {
      method: 'POST',
    });
  },

  getFailedUploads: async (): Promise<FailedUpload[]> => {
    return request<FailedUpload[]>('/failed-uploads');
  },

  deleteFailedUpload: async (id: string): Promise<{ success: boolean }> => {
    return request<{ success: boolean }>(`/failed-uploads/${id}`, { method: 'DELETE' });
  },

  retryResumeParse: async (resumeId: string): Promise<Resume> => {
    return request<Resume>(`/resumes/${resumeId}/retry`, { method: 'POST' });
  },

  getResumeFileUrl: (id: string): string => {
    return `${API_BASE}/resumes/${id}/file`;
  },
};
