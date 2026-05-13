import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Users, Filter, Trash2, Eye, RefreshCw, CheckCircle, XCircle, AlertTriangle, Upload, Clock, Loader2, Briefcase, ChevronDown, Star } from 'lucide-react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { useAppStore } from '../store';
import { toast } from '../lib/toast';
import { confirmAsync } from '../components/ConfirmDialog';
import { FailedUpload } from '../types';
import ScoreBadge from '../components/ScoreBadge';
import SkillTag from '../components/SkillTag';
import Pagination from '../components/Pagination';

const PAGE_SIZE = 10;

export default function ResumesPage() {
  const resumes = useAppStore((state) => state.resumes);
  const resumeTotal = useAppStore((state) => state.resumeTotal);
  const jds = useAppStore((state) => state.jds);
  const selectedJdId = useAppStore((state) => state.selectedJdId);
  const matchResults = useAppStore((state) => state.matchResults);
  const setResumes = useAppStore((state) => state.setResumes);
  const setResumeTotal = useAppStore((state) => state.setResumeTotal);
  const setMatchResults = useAppStore((state) => state.setMatchResults);
  const setJDs = useAppStore((state) => state.setJDs);
  const setSelectedJdId = useAppStore((state) => state.setSelectedJdId);
  const removeResume = useAppStore((state) => state.removeResume);
  const updateResume = useAppStore((state) => state.updateResume);
  const [matching, setMatching] = useState(false);
  const [matchProgress, setMatchProgress] = useState<{ total: number; completed: number } | null>(null);
  const [scoringResumeId, setScoringResumeId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [failedUploads, setFailedUploads] = useState<FailedUpload[]>([]);
  const [jdDropdownOpen, setJdDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(1);

  const selectedJd = useMemo(() => {
    return jds.find(j => j.id === selectedJdId) || null;
  }, [jds, selectedJdId]);

  const filteredMatchResults = useMemo(() => {
    if (!selectedJdId) return [];
    return matchResults.filter(m => m.jdId === selectedJdId);
  }, [matchResults, selectedJdId]);

  const hasParsing = resumes.some(r => r.parseStatus === 'parsing');

  const fetchResumes = useCallback(async (p: number) => {
    const data = await api.getResumes({ page: p, pageSize: PAGE_SIZE, jdId: selectedJdId || undefined });
    setResumes(data.items);
    setResumeTotal(data.total);
    return data;
  }, [selectedJdId, setResumes, setResumeTotal]);

  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      try {
        await fetchResumes(1);
        if (cancelled) return;
        setPage(1);
      } catch {
        if (cancelled) return;
        toast.error('加载简历失败');
      }
      try {
        const jdData = await api.getJDs();
        if (!cancelled) setJDs(jdData.items);
      } catch { /* no JDs */ }
      try {
        const matchData = await api.getAllMatchResults();
        if (!cancelled) setMatchResults(matchData);
      } catch { /* no match results */ }
      try {
        const failedData = await api.getFailedUploads();
        if (!cancelled) setFailedUploads(failedData);
      } catch { /* no failed uploads */ }
    };
    init();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Refetch when selectedJdId changes (e.g. JD dropdown selection)
  useEffect(() => {
    fetchResumes(1).then(() => setPage(1)).catch(() => {});
  }, [selectedJdId]); // eslint-disable-line react-hooks/exhaustive-deps

  const sortedResumes = useMemo(() => {
    if (filteredMatchResults.length === 0) return resumes;
    return [...resumes].sort((a, b) => {
      const resultA = filteredMatchResults.find(m => m.resumeId === a.id);
      const resultB = filteredMatchResults.find(m => m.resumeId === b.id);
      return (resultB?.overallScore || 0) - (resultA?.overallScore || 0);
    });
  }, [resumes, filteredMatchResults]);

  const loadMatchResultsForJd = async (jdId: string) => {
    try {
      const results = await api.getMatchResultsByJd(jdId);
      setMatchResults(prev => [...prev.filter(m => m.jdId !== jdId), ...results]);
    } catch { /* no match results for this JD */ }
  };

  const handleSelectJd = async (jdId: string) => {
    setSelectedJdId(jdId);
    setJdDropdownOpen(false);
    setPage(1);
    try {
      const data = await api.getResumes({ page: 1, pageSize: PAGE_SIZE, jdId });
      setResumes(data.items);
      setResumeTotal(data.total);
    } catch {
      toast.error('加载简历失败');
    }
    const hasResultsForJd = matchResults.some(m => m.jdId === jdId);
    if (!hasResultsForJd) {
      loadMatchResultsForJd(jdId);
    }
  };

  usePolling(() => {
    fetchResumes(page);
  }, hasParsing);

  usePolling(async () => {
    if (!selectedJdId) return;
    try {
      const progress = await api.getMatchProgress(selectedJdId);
      setMatchProgress(progress);
    } catch {
      // progress endpoint unavailable yet
    }
  }, matching && !!selectedJdId);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setJdDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMatch = async () => {
    if (!selectedJdId || !selectedJd) {
      toast.warning('请先选择一个职位');
      return;
    }

    setMatching(true);
    setMatchProgress(null);
    try {
      const response = await api.matchResumes({ jdId: selectedJdId });
      toast.success(`匹配完成，共 ${response.results.length} 份简历`);
      setMatchResults(prev => [...prev.filter(m => m.jdId !== selectedJdId), ...response.results]);
    } catch {
      toast.error('匹配失败，请重试');
    } finally {
      setMatching(false);
      setMatchProgress(null);
    }
  };

  const handleScoreSingle = async (resumeId: string) => {
    if (!selectedJdId) {
      toast.warning('请先选择一个职位');
      return;
    }

    setScoringResumeId(resumeId);
    try {
      const result = await api.scoreSingleResume(resumeId, selectedJdId);
      toast.success('评分完成');
      setMatchResults(prev => [
        ...prev.filter(m => !(m.resumeId === resumeId && m.jdId === selectedJdId)),
        result
      ]);
    } catch {
      toast.error('评分失败，请重试');
    } finally {
      setScoringResumeId(null);
    }
  };

  const handleRetry = async (resumeId: string) => {
    setRetryingId(resumeId);
    try {
      const updated = await api.retryResumeParse(resumeId);
      updateResume(resumeId, updated);
      toast.success('简历重新解析完成');
    } catch {
      toast.error('重新解析失败');
    } finally {
      setRetryingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    const confirmed = await confirmAsync('确定要删除这份简历吗？');
    if (!confirmed) return;
    try {
      await api.deleteResume(id);
      const isLastOnPage = sortedResumes.length <= 1;
      removeResume(id);
      if (isLastOnPage && page > 1) {
        const newPage = page - 1;
        setPage(newPage);
        const data = await api.getResumes({ page: newPage, pageSize: PAGE_SIZE, jdId: selectedJdId || undefined });
        setResumes(data.items);
        setResumeTotal(data.total);
      }
      toast.success('简历已删除');
    } catch {
      toast.error('删除失败，请重试');
    }
  };

  const handleDeleteFailed = async (id: string) => {
    try {
      await api.deleteFailedUpload(id);
      setFailedUploads(failedUploads.filter(f => f.id !== id));
    } catch {
      toast.error('删除失败记录失败');
    }
  };

  const handlePageChange = async (newPage: number) => {
    setPage(newPage);
    try {
      const data = await api.getResumes({ page: newPage, pageSize: PAGE_SIZE, jdId: selectedJdId || undefined });
      setResumes(data.items);
      setResumeTotal(data.total);
    } catch {
      toast.error('加载失败');
    }
  };

  const parsingCount = resumes.filter(r => r.parseStatus === 'parsing').length;
  const completedCount = resumes.filter(r => r.parseStatus === 'completed').length;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">简历列表</h1>
          <p className="text-gray-600">
            共 {resumeTotal} 份简历
            {parsingCount > 0 && (
              <span className="ml-2 text-amber-600">
                ({parsingCount} 份解析中)
              </span>
            )}
          </p>
        </div>
        {resumeTotal > 0 && (
          <div className="flex items-center space-x-4">
            {matching && matchProgress && matchProgress.total > 0 && (
              <div className="flex items-center space-x-3">
                <div className="w-48">
                  <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                    <span>匹配进度</span>
                    <span>{matchProgress.completed}/{matchProgress.total}</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-secondary transition-all duration-500"
                      style={{ width: `${(matchProgress.completed / matchProgress.total) * 100}%` }}
                    />
                  </div>
                </div>
                <Loader2 className="h-4 w-4 text-secondary animate-spin" />
              </div>
            )}
            <button
              onClick={handleMatch}
              disabled={matching || completedCount === 0 || !selectedJdId}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg shadow-sm text-white bg-secondary hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              {matching ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  匹配中...
                </>
              ) : (
                <>
                  <Filter className="h-4 w-4 mr-2" />
                  开始匹配
                </>
              )}
            </button>
          </div>
        )}
      </div>

      <div className="mb-6" ref={dropdownRef}>
        <label className="block text-sm font-medium text-gray-700 mb-2">选择职位</label>
        <div className="relative">
          <button
            onClick={() => setJdDropdownOpen(!jdDropdownOpen)}
            className="w-full max-w-md flex items-center justify-between px-4 py-2.5 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 transition-colors text-left"
          >
            <div className="flex items-center">
              <Briefcase className="h-4 w-4 text-gray-400 mr-2" />
              {selectedJd ? (
                <span className="text-gray-900">{selectedJd.title}</span>
              ) : (
                <span className="text-gray-400">请选择要匹配的职位...</span>
              )}
            </div>
            <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${jdDropdownOpen ? 'rotate-180' : ''}`} />
          </button>
          {jdDropdownOpen && (
            <div className="absolute z-10 mt-1 w-full max-w-md bg-white rounded-lg shadow-lg border border-gray-200 py-1 max-h-60 overflow-auto">
              {jds.length === 0 ? (
                <div className="px-4 py-3 text-sm text-gray-500">
                  暂无职位，请先在"职位管理"中添加
                </div>
              ) : (
                jds.map((jd) => (
                  <button
                    key={jd.id}
                    onClick={() => handleSelectJd(jd.id)}
                    className={`w-full text-left px-4 py-2.5 hover:bg-blue-50 transition-colors ${
                      selectedJdId === jd.id ? 'bg-blue-50 text-secondary' : 'text-gray-700'
                    }`}
                  >
                    <div className="font-medium">{jd.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {jd.keywords.length} 个关键词 · {filteredMatchResults.filter(m => m.jdId === jd.id).length} 个匹配结果
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
        {!selectedJdId && jds.length > 0 && (
          <p className="mt-1 text-xs text-amber-600">请选择一个职位以查看匹配结果</p>
        )}
        {jds.length === 0 && (
          <p className="mt-1 text-xs text-gray-500">
            <Link to="/jd" className="text-secondary hover:underline">前往添加职位</Link>
          </p>
        )}
      </div>

      {resumes.length === 0 ? (
        <div className="text-center py-16">
          <Users className="mx-auto h-16 w-16 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {selectedJdId ? '该职位下暂无简历' : '还没有简历'}
          </h3>
          <p className="text-gray-500 mb-4">
            {selectedJdId ? '请上传简历并关联该职位' : '上传简历开始筛选吧'}
          </p>
          <Link
            to="/"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-secondary hover:bg-blue-600"
          >
            上传简历
          </Link>
        </div>
      ) : (
        <div className="grid gap-6">
          {sortedResumes.map((resume) => {
            const matchResult = filteredMatchResults.find(m => m.resumeId === resume.id);
            const isParsing = resume.parseStatus === 'parsing';
            const isFailed = resume.parseStatus === 'failed';
            const resumeKeywords = matchResult?.keywordMatches || [];
            const resumeMissingKeywords = matchResult?.missingKeywords || [];
            const isScoring = scoringResumeId === resume.id;
            return (
              <div key={resume.id} className={`bg-white rounded-lg shadow-sm border p-6 hover:shadow-md transition-shadow ${isParsing ? 'border-amber-200 bg-amber-50/30' : isFailed ? 'border-red-200 bg-red-50/30' : 'border-gray-200'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-4">
                    {matchResult && (
                      <ScoreBadge score={matchResult.overallScore} confidence={matchResult.confidence} />
                    )}
                    <div>
                      <div className="flex items-center space-x-2">
                        <h3 className="text-lg font-semibold text-gray-900">{resume.name}</h3>
                        {isParsing && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            解析中
                          </span>
                        )}
                        {isFailed && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                            <XCircle className="h-3 w-3 mr-1" />
                            解析失败
                          </span>
                        )}
                      </div>
                      <p className="text-gray-400 text-xs mt-0.5">{resume.filename}</p>
                      {!isParsing && !isFailed && (
                        <p className="text-gray-500 text-sm">{resume.email} · {resume.phone}</p>
                      )}
                      <div className="mt-2">
                        {!isParsing && !isFailed ? (
                          <>
                            <p className="text-sm text-gray-600">
                              {resume.education} · {resume.experience}年经验
                            </p>
                            <p className="text-sm text-gray-500 mt-1 line-clamp-2">{resume.summary}</p>
                          </>
                        ) : isParsing ? (
                          <p className="text-sm text-amber-600 flex items-center">
                            <Clock className="h-4 w-4 mr-1" />
                            正在解析简历内容，请稍候...
                          </p>
                        ) : null}
                      </div>
                      {!isParsing && !isFailed && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {resume.skills.slice(0, 5).map((skill) => (
                            <SkillTag
                              key={skill}
                              skill={skill}
                              matched={selectedJdId ? resumeKeywords.some(
                                kw => kw.toLowerCase() === skill.toLowerCase()
                              ) : resume.keywordMatches?.some(
                                kw => kw.toLowerCase() === skill.toLowerCase()
                              )}
                            />
                          ))}
                          {resume.skills.length > 5 && (
                            <span className="text-xs text-gray-500">+{resume.skills.length - 5} 更多</span>
                          )}
                        </div>
                      )}
                      {selectedJdId && resumeKeywords.length > 0 && (
                        <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-100">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-semibold text-gray-700">关键词匹配（{selectedJd?.title}）</span>
                            <span className="text-xs font-medium">
                              <span className="text-green-600">{resumeKeywords.length}</span>
                              <span className="text-gray-400"> / </span>
                              <span className="text-gray-600">{resumeKeywords.length + resumeMissingKeywords.length}</span>
                            </span>
                          </div>
                          {resumeKeywords.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 mb-1.5">
                              {resumeKeywords.map((kw) => (
                                <span key={kw} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                  <CheckCircle className="h-3 w-3 mr-1" />
                                  {kw}
                                </span>
                              ))}
                            </div>
                          )}
                          {resumeMissingKeywords.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                              {resumeMissingKeywords.slice(0, 5).map((kw) => (
                                <span key={kw} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-600">
                                  <XCircle className="h-3 w-3 mr-1" />
                                  {kw}
                                </span>
                              ))}
                              {resumeMissingKeywords.length > 5 && (
                                <span className="text-xs text-gray-400 self-center">+{resumeMissingKeywords.length - 5}</span>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {selectedJdId && !isParsing && !isFailed && (
                      <button
                        onClick={() => handleScoreSingle(resume.id)}
                        disabled={isScoring}
                        className={`p-2 transition-colors ${
                          matchResult
                            ? 'text-gray-400 hover:text-blue-500'
                            : 'text-blue-500 hover:text-blue-600'
                        }`}
                        title={matchResult ? '重新评分' : '评分'}
                      >
                        {isScoring ? (
                          <Loader2 className="h-5 w-5 animate-spin" />
                        ) : matchResult ? (
                          <RefreshCw className="h-5 w-5" />
                        ) : (
                          <Star className="h-5 w-5" />
                        )}
                      </button>
                    )}
                    <Link
                      to={`/resumes/${resume.id}${selectedJdId ? `?jdId=${selectedJdId}` : ''}`}
                      className="p-2 text-gray-400 hover:text-secondary transition-colors"
                    >
                      <Eye className="h-5 w-5" />
                    </Link>
                    {isFailed && (
                      <button
                        onClick={() => handleRetry(resume.id)}
                        disabled={retryingId === resume.id}
                        className="p-2 text-amber-500 hover:text-amber-600 transition-colors"
                        title="重新解析"
                      >
                        {retryingId === resume.id ? (
                          <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                          <RefreshCw className="h-5 w-5" />
                        )}
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(resume.id)}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {resumeTotal > PAGE_SIZE && (
        <Pagination
          page={page}
          totalPages={Math.ceil(resumeTotal / PAGE_SIZE)}
          total={resumeTotal}
          pageSize={PAGE_SIZE}
          onPageChange={handlePageChange}
        />
      )}

      {failedUploads.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center space-x-2 mb-4">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-gray-900">上传失败记录</h2>
            <span className="text-sm text-gray-500">({failedUploads.length})</span>
          </div>
          <div className="bg-white rounded-lg shadow-sm border border-amber-200 divide-y divide-gray-100">
            {failedUploads.map((failed) => (
              <div key={failed.id} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center space-x-3">
                  <XCircle className="h-5 w-5 text-red-400 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{failed.filename}</p>
                    <p className="text-xs text-red-500">{failed.error}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Link
                    to="/"
                    className="p-1 text-gray-400 hover:text-secondary transition-colors"
                    title="重新上传"
                  >
                    <Upload className="h-4 w-4" />
                  </Link>
                  <button
                    onClick={() => handleDeleteFailed(failed.id)}
                    className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                    title="删除记录"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
