import { Resume, JD, ScoringCriterion, MatchResult, BatchUploadResponse, MatchRequest, MatchResponse, FailedUpload } from './types';

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
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export const api = {
  uploadResumesBatch: async (files: File[]): Promise<BatchUploadResponse> => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    const response = await fetch(`${API_BASE}/upload/batch`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  },

  getResumes: async (): Promise<Resume[]> => {
    return request<Resume[]>('/resumes');
  },

  getResume: async (id: string): Promise<Resume> => {
    return request<Resume>(`/resumes/${id}`);
  },

  deleteResume: async (id: string): Promise<{ success: boolean }> => {
    return request<{ success: boolean }>(`/resumes/${id}`, { method: 'DELETE' });
  },

  createJD: async (data: { title: string; description: string; keywords: string[]; scoringCriteria?: ScoringCriterion[] }): Promise<JD> => {
    return request<JD>('/jds', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getJDs: async (): Promise<JD[]> => {
    return request<JD[]>('/jds');
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

  getFailedUploads: async (): Promise<FailedUpload[]> => {
    return request<FailedUpload[]>('/failed-uploads');
  },

  deleteFailedUpload: async (id: string): Promise<{ success: boolean }> => {
    return request<{ success: boolean }>(`/failed-uploads/${id}`, { method: 'DELETE' });
  },
};
