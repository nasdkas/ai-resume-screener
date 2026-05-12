import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, FileText, Briefcase, GraduationCap, CheckCircle, XCircle, Loader2, RefreshCw, ThumbsUp, ThumbsDown, Target, FolderOpen, ExternalLink } from 'lucide-react';
import { api } from '../api';
import { useAppStore } from '../store';
import { Resume, MatchResult } from '../types';
import ScoreBadge from '../components/ScoreBadge';
import SkillTag from '../components/SkillTag';

export default function ResumeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const jdIdFromUrl = searchParams.get('jdId');
  const [resume, setResume] = useState<Resume | null>(null);
  const [loading, setLoading] = useState(true);
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const [scoring, setScoring] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selectedJdId = useAppStore((state) => state.selectedJdId);
  const jds = useAppStore((state) => state.jds);
  const setMatchResults = useAppStore((state) => state.setMatchResults);
  const activeJdId = jdIdFromUrl || selectedJdId;

  const selectedJd = jds.find(j => j.id === activeJdId) || null;

  const refreshResume = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api.getResume(id);
      setResume(data);
    } catch (error) {
      console.error('Failed to refresh resume:', error);
    }
  }, [id]);

  useEffect(() => {
    const loadData = async () => {
      if (!id) return;
      try {
        const resumeData = await api.getResume(id);
        setResume(resumeData);
      } catch (error) {
        console.error('Failed to load resume:', error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [id]);

  useEffect(() => {
    const loadMatchResult = async () => {
      if (!id || !activeJdId) {
        setMatchResult(null);
        return;
      }
      try {
        const result = await api.getMatchResult(id, activeJdId);
        setMatchResult(result);
      } catch {
        setMatchResult(null);
      }
    };
    loadMatchResult();
  }, [id, activeJdId]);

  useEffect(() => {
    if (resume?.parseStatus === 'parsing') {
      if (pollingRef.current) return;
      pollingRef.current = setInterval(() => {
        refreshResume();
      }, 3000);
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [resume?.parseStatus, refreshResume]);

  const handleRescore = async () => {
    if (!id || !activeJdId) return;
    setScoring(true);
    try {
      const result = await api.scoreSingleResume(id, activeJdId);
      setMatchResult(result);
      setMatchResults(prev => [
        ...prev.filter(m => !(m.resumeId === id && m.jdId === activeJdId)),
        result
      ]);
    } catch (error) {
      console.error('Rescore failed:', error);
      alert('评分失败，请重试');
    } finally {
      setScoring(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-secondary"></div>
      </div>
    );
  }

  if (!resume) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500">简历未找到</p>
      </div>
    );
  }

  const isParsing = resume.parseStatus === 'parsing';
  const isFailed = resume.parseStatus === 'failed';

  const resumeKeywords = matchResult?.keywordMatches || [];
  const resumeMissingKeywords = matchResult?.missingKeywords || [];

  return (
    <div>
      <button
        onClick={() => navigate('/resumes')}
        className="inline-flex items-center text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        返回列表
      </button>

      {isParsing && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center space-x-3">
          <Loader2 className="h-5 w-5 text-amber-500 animate-spin" />
          <div>
            <p className="text-sm font-medium text-amber-800">正在解析简历</p>
            <p className="text-xs text-amber-600">AI 正在提取简历信息，请稍候...</p>
          </div>
        </div>
      )}

      {isFailed && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-3">
          <XCircle className="h-5 w-5 text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-800">简历解析失败</p>
            <p className="text-xs text-red-600">请尝试重新上传此简历文件</p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-start space-x-4">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-primary rounded-full flex items-center justify-center">
                <span className="text-white text-2xl font-bold">
                  {isParsing ? '?' : resume.name.charAt(0)}
                </span>
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h1 className="text-2xl font-bold text-gray-900">{resume.name}</h1>
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
                <button
                  onClick={() => window.open(api.getResumeFileUrl(resume.id), '_blank')}
                  className="flex items-center text-gray-400 text-sm hover:text-blue-500 transition-colors group"
                  title="点击预览简历原文件"
                >
                  <FileText className="h-3.5 w-3.5 mr-1" />
                  <span className="group-hover:underline">{resume.originalFilename || resume.filename}</span>
                  <ExternalLink className="h-3 w-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
                {!isParsing && !isFailed && (
                  <>
                    <p className="text-gray-500">{resume.email}</p>
                    <p className="text-gray-500">{resume.phone}</p>
                  </>
                )}
              </div>
            </div>
          </div>

          {!isParsing && !isFailed ? (
            <>
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <GraduationCap className="h-5 w-5 text-gray-400" />
                  <h2 className="text-lg font-semibold text-gray-900">基本信息</h2>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-sm text-gray-500">最高学历</span>
                    <p className="font-medium text-gray-900">{resume.education}</p>
                  </div>
                  <div>
                    <span className="text-sm text-gray-500">工作经验</span>
                    <p className="font-medium text-gray-900">{resume.experience} 年</p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <Briefcase className="h-5 w-5 text-gray-400" />
                  <h2 className="text-lg font-semibold text-gray-900">技能</h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  {resume.skills.map((skill) => (
                    <SkillTag
                      key={skill}
                      skill={skill}
                      matched={activeJdId ? resumeKeywords.some(
                        kw => kw.toLowerCase() === skill.toLowerCase()
                      ) : resume.keywordMatches?.some(
                        kw => kw.toLowerCase() === skill.toLowerCase()
                      )}
                    />
                  ))}
                </div>
              </div>

              {activeJdId && (resumeKeywords.length > 0 || resumeMissingKeywords.length > 0) && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <div className="flex items-center space-x-2 mb-4">
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    <h2 className="text-lg font-semibold text-gray-900">关键词匹配</h2>
                    {selectedJd && (
                      <span className="text-xs text-gray-400 ml-1">（{selectedJd.title}）</span>
                    )}
                    <span className="text-xs font-medium ml-auto">
                      <span className="text-green-600">{resumeKeywords.length}</span>
                      <span className="text-gray-400"> / </span>
                      <span className="text-gray-600">{resumeKeywords.length + resumeMissingKeywords.length}</span>
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {resumeKeywords.map((kw) => (
                      <span key={kw} className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        {kw}
                      </span>
                    ))}
                  </div>
                  {resumeMissingKeywords.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {resumeMissingKeywords.map((kw) => (
                        <span key={kw} className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-600">
                          <XCircle className="h-3 w-3 mr-1" />
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <FileText className="h-5 w-5 text-gray-400" />
                  <h2 className="text-lg font-semibold text-gray-900">个人简介</h2>
                </div>
                <p className="text-gray-700 leading-relaxed">{resume.summary}</p>
              </div>
            </>
          ) : isParsing ? (
            <div className="bg-white rounded-lg shadow-sm border border-amber-200 p-8 text-center">
              <Loader2 className="h-12 w-12 text-amber-500 animate-spin mx-auto mb-4" />
              <p className="text-gray-600 font-medium">正在解析简历内容</p>
              <p className="text-sm text-gray-400 mt-1">AI 正在提取姓名、技能、经验等信息...</p>
            </div>
          ) : null}
        </div>

        <div className="space-y-6">
          {matchResult ? (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <h2 className="text-lg font-semibold text-gray-900">匹配评分</h2>
                  {selectedJd && (
                    <span className="text-xs text-gray-400">（{selectedJd.title}）</span>
                  )}
                </div>
                <button
                  onClick={handleRescore}
                  disabled={scoring}
                  className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300 transition-colors disabled:opacity-50"
                >
                  {scoring ? (
                    <>
                      <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      评分中...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-3 w-3 mr-1" />
                      重新评分
                    </>
                  )}
                </button>
              </div>
              <div className="flex justify-center mb-6">
                <ScoreBadge score={matchResult.overallScore} size="lg" />
              </div>

              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600 flex items-center"><Briefcase className="h-3.5 w-3.5 mr-1.5 text-blue-500" />技能匹配 <span className="text-gray-400 ml-1">(35%)</span></span>
                    <span className="font-medium">{matchResult.skillMatch}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all"
                      style={{ width: `${matchResult.skillMatch}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600 flex items-center"><GraduationCap className="h-3.5 w-3.5 mr-1.5 text-green-500" />经验匹配 <span className="text-gray-400 ml-1">(20%)</span></span>
                    <span className="font-medium">{matchResult.experienceMatch}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 transition-all"
                      style={{ width: `${matchResult.experienceMatch}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600 flex items-center"><Target className="h-3.5 w-3.5 mr-1.5 text-amber-500" />关键词匹配 <span className="text-gray-400 ml-1">(20%)</span></span>
                    <span className="font-medium">{matchResult.keywordMatch}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500 transition-all"
                      style={{ width: `${matchResult.keywordMatch}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600 flex items-center"><FolderOpen className="h-3.5 w-3.5 mr-1.5 text-cyan-500" />项目经验匹配 <span className="text-gray-400 ml-1">(15%)</span></span>
                    <span className="font-medium">{matchResult.projectMatch}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan-500 transition-all"
                      style={{ width: `${matchResult.projectMatch}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600 flex items-center"><GraduationCap className="h-3.5 w-3.5 mr-1.5 text-purple-500" />学历匹配 <span className="text-gray-400 ml-1">(10%)</span></span>
                    <span className="font-medium">{matchResult.educationMatch}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-500 transition-all"
                      style={{ width: `${matchResult.educationMatch}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-gray-200">
                <h3 className="font-medium text-gray-900 mb-3">关键词匹配</h3>
                <div className="space-y-2">
                  {matchResult.keywordMatches.map((kw) => (
                    <div key={kw} className="flex items-center text-sm text-green-700">
                      <CheckCircle className="h-4 w-4 mr-2" />
                      {kw}
                    </div>
                  ))}
                  {matchResult.missingKeywords.map((kw) => (
                    <div key={kw} className="flex items-center text-sm text-red-700">
                      <XCircle className="h-4 w-4 mr-2" />
                      {kw}
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-gray-200">
                <h3 className="font-medium text-gray-900 mb-2">AI 分析</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{matchResult.analysis}</p>
              </div>

              {matchResult.strengths && matchResult.strengths.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h3 className="font-medium text-gray-900 mb-2 flex items-center"><ThumbsUp className="h-4 w-4 mr-1.5 text-green-500" />候选人优势</h3>
                  <ul className="space-y-1.5">
                    {matchResult.strengths.map((s, i) => (
                      <li key={i} className="flex items-start text-sm text-green-700">
                        <CheckCircle className="h-3.5 w-3.5 mr-2 mt-0.5 flex-shrink-0" />
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {matchResult.weaknesses && matchResult.weaknesses.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h3 className="font-medium text-gray-900 mb-2 flex items-center"><ThumbsDown className="h-4 w-4 mr-1.5 text-red-500" />候选人不足</h3>
                  <ul className="space-y-1.5">
                    {matchResult.weaknesses.map((w, i) => (
                      <li key={i} className="flex items-start text-sm text-red-600">
                        <XCircle className="h-3.5 w-3.5 mr-2 mt-0.5 flex-shrink-0" />
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
              <p className="text-gray-500">暂无匹配结果</p>
              <p className="text-sm text-gray-400 mt-1">
                {activeJdId
                  ? '点击下方按钮开始评分'
                  : '请先选择一个职位，再进行匹配'}
              </p>
              {activeJdId && !isParsing && !isFailed && (
                <button
                  onClick={handleRescore}
                  disabled={scoring}
                  className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg shadow-sm text-white bg-secondary hover:bg-blue-600 transition-colors disabled:opacity-50"
                >
                  {scoring ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      评分中...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      开始评分
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
