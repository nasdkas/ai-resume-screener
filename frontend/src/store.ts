import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Resume, JD, MatchResult } from './types';
import type { Toast } from './components/Toast';
import type { ConfirmDialogState } from './components/ConfirmDialog';

interface AppState {
  resumes: Resume[];
  resumeTotal: number;
  jds: JD[];
  selectedJdId: string | null;
  matchResults: MatchResult[];
  loading: boolean;
  error: string | null;
  toasts: Toast[];
  confirmDialog: ConfirmDialogState;

  setResumes: (resumes: Resume[]) => void;
  setResumeTotal: (total: number) => void;
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
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  setConfirmDialog: (state: ConfirmDialogState) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      resumes: [],
      resumeTotal: 0,
      jds: [],
      selectedJdId: null,
      matchResults: [],
      loading: false,
      error: null,
      toasts: [],
      confirmDialog: { open: false, message: '' },

      setResumes: (resumes) => set({ resumes }),
      setResumeTotal: (resumeTotal) => set({ resumeTotal }),
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
        resumeTotal: Math.max(0, state.resumeTotal - 1),
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
      addToast: (toast) => {
        const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
      },
      removeToast: (id) => set((state) => ({
        toasts: state.toasts.filter(t => t.id !== id)
      })),
      setConfirmDialog: (state) => set({ confirmDialog: state }),
    }),
    {
      name: 'app-storage',
      partialize: (state) => ({
        selectedJdId: state.selectedJdId,
      }),
    }
  )
);
