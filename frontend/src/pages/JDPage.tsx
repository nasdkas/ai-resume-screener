import { useState, useEffect } from 'react';
import { Plus, Save, CheckCircle, Trash2, Edit2, X, Briefcase } from 'lucide-react';
import { api } from '../api';
import { useAppStore } from '../store';
import { toast } from '../lib/toast';
import { confirmAsync } from '../components/ConfirmDialog';
import { JD, ScoringCriterion } from '../types';

interface JDFormData {
  title: string;
  description: string;
  keywords: string[];
  scoringCriteria: ScoringCriterion[];
}

const emptyForm: JDFormData = { title: '', description: '', keywords: [], scoringCriteria: [] };

export default function JDPage() {
  const jds = useAppStore((state) => state.jds);
  const setJDs = useAppStore((state) => state.setJDs);
  const addJD = useAppStore((state) => state.addJD);
  const updateJDStore = useAppStore((state) => state.updateJD);
  const removeJD = useAppStore((state) => state.removeJD);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<JDFormData>(emptyForm);
  const [keywordInput, setKeywordInput] = useState('');
  const [criterionInput, setCriterionInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const loadJDs = async () => {
      try {
        const data = await api.getJDs();
        setJDs(data.items);
      } catch (error) {
        console.log('Failed to load JDs');
      }
    };
    loadJDs();
  }, [setJDs]);

  const startCreate = () => {
    setIsNew(true);
    setEditingId(null);
    setForm(emptyForm);
    setKeywordInput('');
    setCriterionInput('');
  };

  const startEdit = (jd: JD) => {
    setIsNew(false);
    setEditingId(jd.id);
    setForm({
      title: jd.title,
      description: jd.description,
      keywords: [...jd.keywords],
      scoringCriteria: jd.scoringCriteria ? [...jd.scoringCriteria] : [],
    });
    setKeywordInput('');
    setCriterionInput('');
  };

  const cancelEdit = () => {
    setIsNew(false);
    setEditingId(null);
    setForm(emptyForm);
    setKeywordInput('');
    setCriterionInput('');
  };

  const addKeyword = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && keywordInput.trim()) {
      const newKeywords = keywordInput
        .split(/[,，、\s]+/)
        .map(k => k.trim())
        .filter(k => k && !form.keywords.includes(k));
      if (newKeywords.length > 0) {
        setForm({ ...form, keywords: [...form.keywords, ...newKeywords] });
      }
      setKeywordInput('');
    }
  };

  const removeKeyword = (keyword: string) => {
    setForm({ ...form, keywords: form.keywords.filter(k => k !== keyword) });
  };

  const addCriterion = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && criterionInput.trim()) {
      const exists = form.scoringCriteria.some(c => c.item === criterionInput.trim());
      if (!exists) {
        setForm({
          ...form,
          scoringCriteria: [...form.scoringCriteria, { item: criterionInput.trim(), weight: '必须' }],
        });
      }
      setCriterionInput('');
    }
  };

  const removeCriterion = (item: string) => {
    setForm({ ...form, scoringCriteria: form.scoringCriteria.filter(c => c.item !== item) });
  };

  const handleSave = async () => {
    if (!form.title.trim() || !form.description.trim()) return;
    setSaving(true);
    try {
      if (isNew) {
        const savedJD = await api.createJD(form);
        addJD(savedJD);
        setIsNew(false);
      } else if (editingId) {
        const savedJD = await api.updateJD(editingId, form);
        updateJDStore(editingId, savedJD);
        setEditingId(null);
      }
      setForm(emptyForm);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      toast.error('保存职位失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (jd: JD) => {
    const confirmed = await confirmAsync(`确定要删除职位"${jd.title}"吗？相关的匹配结果也会被删除。`);
    if (!confirmed) return;
    try {
      await api.deleteJD(jd.id);
      removeJD(jd.id);
      if (editingId === jd.id) {
        setEditingId(null);
        setForm(emptyForm);
      }
    } catch (error) {
      toast.error('删除失败');
      console.error(error);
    }
  };

  const isEditing = isNew || editingId !== null;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">职位描述管理</h1>
          <p className="text-gray-600">管理多个职位，每个职位独立匹配评分</p>
        </div>
        {!isEditing && (
          <button
            onClick={startCreate}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg shadow-sm text-white bg-secondary hover:bg-blue-600 transition-colors"
          >
            <Plus className="h-4 w-4 mr-2" />
            添加职位
          </button>
        )}
      </div>

      {isEditing && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              {isNew ? '新建职位' : '编辑职位'}
            </h2>
            <button
              onClick={cancelEdit}
              className="p-1 text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                职位名称
              </label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-secondary focus:border-transparent"
                placeholder="例如：高级前端工程师"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                职位描述
              </label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={6}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-secondary focus:border-transparent"
                placeholder="请输入职位描述，包括职责、要求等..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                关键词筛选
              </label>
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={addKeyword}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-secondary focus:border-transparent mb-3"
                placeholder="输入关键词后按回车添加，支持逗号分隔多个关键词"
              />
              <div className="flex flex-wrap gap-2">
                {form.keywords.map((keyword) => (
                  <span
                    key={keyword}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800"
                  >
                    {keyword}
                    <button
                      onClick={() => removeKeyword(keyword)}
                      className="ml-2 text-blue-600 hover:text-blue-800"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                JD必须需求
              </label>
              <p className="text-xs text-gray-500 mb-2">
                添加硬性门槛要求，不满足任意一项则直接极低分
              </p>
              <input
                type="text"
                value={criterionInput}
                onChange={(e) => setCriterionInput(e.target.value)}
                onKeyDown={addCriterion}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-secondary focus:border-transparent mb-3"
                placeholder="输入必须需求后按回车添加，如：3年以上Java经验"
              />
              {form.scoringCriteria.length > 0 && (
                <div className="space-y-2">
                  {form.scoringCriteria.map((criterion) => (
                    <div
                      key={criterion.item}
                      className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg"
                    >
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">硬性门槛</span>
                      <span className="flex-1 text-sm text-gray-800">{criterion.item}</span>
                      <button
                        onClick={() => removeCriterion(criterion.item)}
                        className="text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center space-x-3 pt-2">
              <button
                onClick={handleSave}
                disabled={saving || !form.title.trim() || !form.description.trim()}
                className="inline-flex items-center px-6 py-2.5 border border-transparent text-sm font-medium rounded-lg shadow-sm text-white bg-secondary hover:bg-blue-600 transition-colors disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    保存中...
                  </>
                ) : saved ? (
                  <>
                    <CheckCircle className="h-4 w-4 mr-2" />
                    已保存
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    保存职位
                  </>
                )}
              </button>
              <button
                onClick={cancelEdit}
                className="px-4 py-2.5 border border-gray-300 text-sm font-medium rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {jds.length === 0 && !isEditing ? (
        <div className="text-center py-16">
          <Briefcase className="mx-auto h-16 w-16 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">还没有职位描述</h3>
          <p className="text-gray-500 mb-4">添加职位描述，开始简历匹配</p>
          <button
            onClick={startCreate}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-secondary hover:bg-blue-600"
          >
            <Plus className="h-4 w-4 mr-2" />
            添加职位
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {jds.map((jd) => (
            <div
              key={jd.id}
              className={`bg-white rounded-lg shadow-sm border p-5 hover:shadow-md transition-shadow ${
                editingId === jd.id ? 'border-blue-300 ring-1 ring-blue-200' : 'border-gray-200'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-gray-900 truncate">{jd.title}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">{jd.description}</p>
                  {jd.keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {jd.keywords.map((kw) => (
                        <span
                          key={kw}
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}
                  {jd.scoringCriteria && jd.scoringCriteria.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {jd.scoringCriteria.map((c) => (
                        <span
                          key={c.item}
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"
                        >
                          {c.item}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center space-x-1 ml-4">
                  <button
                    onClick={() => startEdit(jd)}
                    className="p-2 text-gray-400 hover:text-secondary transition-colors"
                    title="编辑"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(jd)}
                    className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                    title="删除"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
