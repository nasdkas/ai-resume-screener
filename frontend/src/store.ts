import { create } from 'zustand';
import { Resume, JD, MatchResult } from './types';

interface AppState {
  resumes: Resume[];
  jds: JD[];
  selectedJdId: string | null;
  matchResults: MatchResult[];
  loading: boolean;
  error: string | null;

  setResumes: (resumes: Resume[]) => void;
  setJDs: (jds: JD[]) => void;
  setSelectedJdId: (jdId: string | null) => void;
  setMatchResults: (results: MatchResult[] | ((prev: MatchResult[]) => MatchResult[])) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  addResume: (resume: Resume) => void;
  updateResume: (id: string, updates: Partial<Resume>) => void;
  removeResume: (id: string) => void;
  addJD: (jd: JD) => void;
  updateJD: (id: string, updates: Partial<JD>) => void;
  removeJD: (id: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  resumes: [],
  jds: [],
  selectedJdId: null,
  matchResults: [],
  loading: false,
  error: null,

  setResumes: (resumes) => set({ resumes }),
  setJDs: (jds) => set({ jds }),
  setSelectedJdId: (jdId) => set({ selectedJdId: jdId }),
  setMatchResults: (results) => set((state) => ({
    matchResults: typeof results === 'function' ? results(state.matchResults) : results
  })),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  addResume: (resume) => set((state) => ({ resumes: [...state.resumes, resume] })),
  updateResume: (id, updates) => set((state) => ({
    resumes: state.resumes.map(r => r.id === id ? { ...r, ...updates } : r)
  })),
  removeResume: (id) => set((state) => ({
    resumes: state.resumes.filter(r => r.id !== id),
    matchResults: state.matchResults.filter(m => m.resumeId !== id)
  })),
  addJD: (jd) => set((state) => ({ jds: [...state.jds, jd] })),
  updateJD: (id, updates) => set((state) => ({
    jds: state.jds.map(j => j.id === id ? { ...j, ...updates } : j)
  })),
  removeJD: (id) => set((state) => ({
    jds: state.jds.filter(j => j.id !== id),
    matchResults: state.matchResults.filter(m => m.jdId !== id),
    selectedJdId: state.selectedJdId === id ? (state.jds.find(j => j.id !== id)?.id || null) : state.selectedJdId
  })),
}));
