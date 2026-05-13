# AI 简历筛选助手

基于 LLM 的智能简历筛选应用，支持本地小模型（Ollama）和云端大模型（OpenAI），帮助招聘人员快速解析、评估和匹配候选人简历。

## 功能特性

- 📄 **简历上传与解析** — 支持 PDF、DOCX、TXT 格式，AI 自动提取姓名/技能/经验/学历等结构化信息
- 💾 **原文件存储与预览** — 上传简历自动保存原文件，点击文件名可直接预览
- 📋 **职位描述管理** — 配置职位描述、关键词筛选、自定义评分标准（必须/重要/加分）
- 🤖 **AI 智能匹配评分** — LLM 驱动的多维度评分（技能 35%/经验 25%/项目 20%/关键词 10%/学历 10%）
- 🔍 **双阶段评分** — 门槛检查与维度评分分离，服务端强制封顶，不依赖 LLM 指令遵守能力
- 🏷️ **关键词重要性加权** — "必须"项权重 ×3、"优先"项 ×2，重要关键词对齐更高权重
- 🔗 **关键词语义匹配** — 融合文本精确匹配与 LLM 语义理解，避免同义词遗漏
- 📊 **分数置信度指标** — 基于文本质量、分数方差、模型层级等因子综合计算，提供分数可信度参考
- 🎯 **锚点校准** — Prompt 内嵌校准示例，帮助 LLM 稳定评分尺度
- ✂️ **长简历自动拆分** — Ollama 模式下超长简历自动拆分为多次 LLM 调用，LLM 智能合并结果
- 📱 **响应式设计** — 支持桌面和移动端

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Zustand + React Router |
| 后端 | Python 3.11+ + FastAPI + Pydantic + SQLite |
| LLM | OpenAI API / Ollama（本地部署） |
| 文档解析 | PyPDF2 + python-docx + pdfplumber + PyMuPDF |

## 快速开始

### 1. 环境准备

#### 后端

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

#### 前端

```bash
cd frontend
npm install
```

### 2. 配置环境变量

在 `backend` 目录下创建 `.env` 文件（参考 `.env.example`）：

**使用 Ollama（本地模型）：**

```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=gemma4:e4b
```

**使用 OpenAI（云端模型）：**

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**高级选项（可选）：**

```env
LLM_JSON_MODE=true          # 启用 JSON 模式，输出更稳定
LLM_THINK_MODE=false        # 启用 CoT（思维链），提升复杂推理
RESUME_STORAGE_DIR=./data/resumes  # 简历文件存储目录
```

### 3. 启动应用

#### 启动后端

```bash
cd backend
uvicorn main:app --reload --port 8000
```

后端 API 文档：http://localhost:8000/docs

#### 启动前端

```bash
cd frontend
npm run dev
```

前端访问：http://localhost:5173

## 使用流程

```
配置职位 → 上传简历 → AI 解析 → 选择职位匹配 → 查看评分排序
```

1. **配置职位** — 进入「职位管理」页面，填写职位描述、关键词和评分标准
2. **上传简历** — 在「上传简历」页面拖拽或选择文件，支持批量上传，可选择关联职位自动匹配
3. **AI 解析** — 上传后自动解析，页面实时显示解析进度和结果
4. **开始匹配** — 在「简历列表」页面选择职位，点击「开始匹配」
5. **查看结果** — 按匹配度排序查看简历，点击详情查看完整分析，可预览简历原文件

## 项目结构

```
.
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── components/          # 通用组件（Navbar, ScoreBadge, SkillTag）
│   │   ├── pages/              # 页面组件
│   │   │   ├── UploadPage.tsx     # 简历上传（轮询解析/匹配状态）
│   │   │   ├── JDPage.tsx         # 职位管理（评分标准配置）
│   │   │   ├── ResumesPage.tsx    # 简历列表（匹配/排序/置信度）
│   │   │   └── ResumeDetailPage.tsx # 简历详情（维度分解/置信度/段位）
│   │   ├── api.ts              # API 调用封装
│   │   ├── store.ts            # Zustand 全局状态
│   │   └── types.ts            # TypeScript 类型定义
│   └── package.json
└── backend/                     # FastAPI 后端
    ├── app/
    │   ├── api/
    │   │   └── routes.py        # API 路由
    │   ├── models/
    │   │   └── schemas.py       # Pydantic 数据模型
    │   └── services/
    │       ├── scoring.py       # 评分核心模块（权重/段位/置信度/锚点） ← 新增
    │       ├── llm_service.py   # LLM 调用（双阶段评分/关键词加权/合并）
    │       ├── matcher.py       # 匹配调度（批量/异步/textQuality 透传）
    │       ├── parser.py        # 文件解析（PDF/DOCX/TXT）
    │       ├── storage.py       # SQLite 数据库层
    │       └── file_storage.py  # 简历原文件存储
    ├── data/                    # 数据存储目录（screener.db + resumes/）
    ├── .env.example             # 环境变量示例
    └── requirements.txt
```

## 核心设计

### 评分架构

评分采用**双阶段 + 服务端强制兜底**架构，确保评分规则高可靠：

```
上传简历 → 文本提取 → ┌─ Pass 1: 门槛检查（LLM） → 服务端校验
                      ├─ Pass 2: 维度评分（LLM） → 关键词加权 → 置信度计算 → 存储
                      └──────────────────── 服务端封顶 ≤40（门槛不满足时）
```

#### 评分维度与权重

所有权重定义在 `scoring.py` 单一来源，prompt 和前端自动同步：

| 维度 | 权重 | 说明 |
|------|------|------|
| skillMatch | **35%** | 技术栈重合度、技能深度与广度 |
| experienceMatch | **25%** | 相关领域经验、职责匹配度 |
| projectMatch | **20%** | 项目复杂度、与 JD 业务场景相关性 |
| keywordMatch | **10%** | 加权关键词比例 ×50% + LLM 语义分数 ×50% |
| educationMatch | **10%** | 学历层次要求 |

#### 双阶段评分

**Pass 1 — 硬性门槛检查：**
- 只检查 JD 中配置的「必须满足」项
- 逐项输出通过/不通过及证据
- 无必须项时跳过

**Pass 2 — 维度评分：**
- 接收 Pass 1 结果作为上下文
- 5 维度独立打分（0-100）

**服务端强制兜底：**
- 门槛不满足 → 所有维度分数 ≤ 40（不依赖 LLM 遵守指令）
- overallScore 始终由服务端加权重算（忽略 LLM 的 overall）

### 关键词重要性加权

关键词评分从"匹配数/总数 × 100"升级为：

```
keywordMatch = 加权文本比例 × 50% + LLM 语义分数 × 50%

关键词权重：
  - "必须" 项 × 3.0
  - "优先" 项 × 2.0  
  - 普通关键词 × 1.0
```

同时保留**双通道融合**：
- **文本精确匹配** — 字符串/词边界搜索，精确可靠
- **LLM 语义匹配** — 理解同义词和上下文
- **合并规则** — 任一命中即匹配，两者都缺失才算缺失

### 锚点校准

评分 prompt 中嵌入 3 个校准锚点示例，帮助 LLM 稳定评分尺度：

| 案例 | 描述 | 分数参考 |
|------|------|----------|
| 高度匹配 | 技能 100% 覆盖，项目对口，经验满足 | skill≈95, exp≈90, overall≈91 |
| 基本匹配 | 技能 70% 覆盖，相关但不完全对口 | skill≈72, exp≈65, overall≈68 |
| 完全不匹配 | 背景与 JD 完全无关 | 所有维度 ≤15, overall≈12 |

### 分数置信度

每个匹配结果附带 `confidence`（0.0-1.0），基于 6 个因子：

| 因子 | 权重 | 说明 |
|------|------|------|
| 文本提取质量 | 25% | parser.py 多引擎择优质量评分 |
| 分数方差 | 25% | 五维分数差异大→区分度高→置信度高 |
| 模型层级 | 15% | deepseek/claude > qwen/llama 小模型 |
| 门槛一致性 | 15% | LLM 判断与文本匹配是否一致 |
| 文本长度 | 10% | 极短简历降低置信度 |
| 拆分惩罚 | 10% | 超长文本拆分处理时降低 |

### 小模型优化策略

针对 Ollama 本地小模型（如 qwen3.5）做了以下优化：

| 策略 | 说明 |
|------|------|
| 双阶段拆分解耦 | 门槛检查与维度评分分离，避免复杂指令被忽略 |
| 结构化提示词 + JSON Schema | 约束输出格式，减少解析错误 |
| 锚点校准 | 提供分数参考标准，缓解小模型评分漂移 |
| 提示词压缩 | 移除冗余描述，减少 token 消耗 |
| 长简历拆分 | 超 5000 字符自动拆分两次 LLM 调用 |
| Provider 感知 | OpenAI 模式不拆分，Ollama 模式按阈值拆分 |

### 评分版本兼容

- `scoringVersion: "2.0"` 标记当前评分架构版本
- 数据库 schema 仅做加法迁移，旧数据完全兼容
- 新字段（confidence, thresholdPassed 等）为 optional，旧记录可正常读取

## 数据库

使用 SQLite 作为数据存储（`backend/data/screener.db`），包含四个表：

- **resumes** — 简历基本信息、解析状态、文本内容、文本质量评分
- **jds** — 职位描述、关键词列表、评分标准配置
- **match_results** — 匹配结果（5 维度分数 + 置信度 + 版本号 + 门槛状态）
- **failed_uploads** — 上传失败记录

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 单文件上传简历，可选关联 JD 自动匹配 |
| POST | `/api/upload/batch` | 批量上传简历 |
| GET | `/api/resumes` | 获取简历列表 |
| GET | `/api/resumes/{id}` | 获取简历详情 |
| GET | `/api/resumes/{id}/file` | 获取简历原文件（预览） |
| DELETE | `/api/resumes/{id}` | 删除简历 |
| POST | `/api/jds` | 创建职位 |
| GET | `/api/jds` | 获取职位列表 |
| GET | `/api/jds/{id}` | 获取职位详情 |
| PUT | `/api/jds/{id}` | 更新职位 |
| DELETE | `/api/jds/{id}` | 删除职位 |
| POST | `/api/match` | 执行匹配 |
| GET | `/api/matches/{jd_id}` | 按 JD 获取匹配结果 |
| GET | `/api/matches` | 获取所有匹配结果 |
| GET | `/api/match/{resume_id}/{jd_id}` | 获取单个匹配结果 |
| POST | `/api/match/{resume_id}/{jd_id}` | 对单个简历重新评分 |
| GET | `/api/failed-uploads` | 获取上传失败记录 |
| DELETE | `/api/failed-uploads/{id}` | 删除上传失败记录 |

完整 API 文档请访问 http://localhost:8000/docs

## License

[Apache License 2.0](LICENSE)
