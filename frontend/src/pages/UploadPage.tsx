import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, CheckCircle, XCircle, FileText, Loader2 } from 'lucide-react';
import { api } from '../api';
import { useAppStore } from '../store';
import { UploadResult as UploadResultType } from '../types';

export default function UploadPage() {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState<UploadResultType[]>([]);
  const addResume = useAppStore((state) => state.addResume);
  const updateResume = useAppStore((state) => state.updateResume);
  const resumes = useAppStore((state) => state.resumes);
  const navigate = useNavigate();
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const uploadedIds = uploadResults
    .filter(r => r.success && r.resume)
    .map(r => r.resume!.id);

  const hasParsing = uploadedIds.some(id =>
    resumes.find(r => r.id === id)?.parseStatus === 'parsing'
  );

  const pollParsingResumes = useCallback(async () => {
    for (const id of uploadedIds) {
      const current = resumes.find(r => r.id === id);
      if (!current || current.parseStatus !== 'parsing') continue;
      try {
        const fresh = await api.getResume(id);
        if (fresh.parseStatus !== 'parsing') {
          updateResume(id, fresh);
        }
      } catch {
        console.error(`Failed to poll resume ${id}`);
      }
    }
  }, [uploadedIds, resumes, updateResume]);

  useEffect(() => {
    if (hasParsing) {
      if (pollingRef.current) return;
      pollingRef.current = setInterval(pollParsingResumes, 3000);
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
  }, [hasParsing, pollParsingResumes]);

  const handleFiles = async (files: File[]) => {
    if (files.length === 0) return;

    setUploading(true);
    setUploadResults([]);

    try {
      const response = await api.uploadResumesBatch(files);
      setUploadResults(response.results);

      const submittedResumes = response.results
        .filter(r => r.success && r.resume)
        .map(r => r.resume!);
      submittedResumes.forEach(r => addResume(r));
    } catch (error) {
      console.error('Upload failed:', error);
      setUploadResults(files.map(f => ({
        filename: f.name,
        success: false,
        error: '上传请求失败'
      })));
    } finally {
      setUploading(false);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const onDragLeave = () => {
    setDragOver(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) handleFiles(files);
  };

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) handleFiles(files);
    e.target.value = '';
  };

  const successCount = uploadResults.filter(r => r.success).length;
  const failCount = uploadResults.filter(r => !r.success).length;
  const hasResults = uploadResults.length > 0;

  const getResumeStatus = (result: UploadResultType) => {
    if (!result.success || !result.resume) return 'failed';
    const current = resumes.find(r => r.id === result.resume!.id);
    if (!current) return 'parsing';
    return current.parseStatus;
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">上传简历</h1>
        <p className="text-gray-600">支持 PDF、DOCX 格式，可同时上传多份</p>
      </div>

      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          dragOver
            ? 'border-secondary bg-blue-50'
            : 'border-gray-300 hover:border-secondary'
        }`}
      >
        <Upload className={`mx-auto h-16 w-16 mb-4 ${dragOver ? 'text-secondary' : 'text-gray-400'}`} />

        {uploading ? (
          <div className="space-y-2">
            <p className="text-lg text-gray-600">正在上传文件...</p>
            <div className="animate-pulse h-2 bg-gray-200 rounded w-48 mx-auto"></div>
          </div>
        ) : (
          <div>
            <p className="text-lg text-gray-600 mb-4">
              拖拽文件到此处，或<span className="text-secondary cursor-pointer ml-1">点击选择文件</span>
            </p>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              multiple
              onChange={onChange}
              className="hidden"
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="inline-block bg-secondary hover:bg-blue-600 text-white font-medium py-2 px-6 rounded-lg transition-colors cursor-pointer"
            >
              选择文件
            </label>
          </div>
        )}
      </div>

      {hasResults && !uploading && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">上传结果</h2>
            {successCount > 0 && !hasParsing && (
              <button
                onClick={() => navigate('/resumes')}
                className="text-sm text-secondary hover:text-blue-600 font-medium"
              >
                查看简历列表 →
              </button>
            )}
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 divide-y divide-gray-100">
            {uploadResults.map((result, index) => {
              const status = getResumeStatus(result);
              const resume = result.resume ? resumes.find(r => r.id === result.resume!.id) : null;
              return (
                <div key={index} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <FileText className="h-5 w-5 text-gray-400 flex-shrink-0" />
                      <span className="text-sm text-gray-900 truncate max-w-xs">{result.filename}</span>
                    </div>
                    {status === 'parsing' ? (
                      <span className="inline-flex items-center text-sm text-amber-600 font-medium">
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                        解析中
                      </span>
                    ) : status === 'completed' ? (
                      <span className="inline-flex items-center text-sm text-green-600 font-medium">
                        <CheckCircle className="h-4 w-4 mr-1" />
                        解析完成
                      </span>
                    ) : status === 'failed' ? (
                      <span className="inline-flex items-center text-sm text-red-600 font-medium">
                        <XCircle className="h-4 w-4 mr-1" />
                        解析失败
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-sm text-red-600 font-medium">
                        <XCircle className="h-4 w-4 mr-1" />
                        {result.error || '上传失败'}
                      </span>
                    )}
                  </div>
                  {status === 'completed' && resume && (
                    <div className="mt-2 ml-8">
                      <p className="text-sm text-gray-700">
                        <span className="font-medium">{resume.name}</span>
                        {resume.email && <span className="text-gray-400 ml-2">{resume.email}</span>}
                        {resume.experience > 0 && <span className="text-gray-400 ml-2">{resume.experience}年经验</span>}
                      </p>
                      {resume.skills.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {resume.skills.slice(0, 5).map((skill) => (
                            <span key={skill} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                              {skill}
                            </span>
                          ))}
                          {resume.skills.length > 5 && (
                            <span className="text-xs text-gray-400">+{resume.skills.length - 5}</span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-center space-x-4 text-sm">
            {hasParsing && (
              <span className="text-amber-600 flex items-center">
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                正在解析中，请稍候...
              </span>
            )}
            {!hasParsing && successCount > 0 && (
              <span className="text-green-600 flex items-center">
                <CheckCircle className="h-4 w-4 mr-1" />
                {successCount} 份简历解析完成
              </span>
            )}
            {failCount > 0 && (
              <span className="text-red-600">✗ {failCount} 份失败</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
