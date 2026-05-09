# AI 简历筛选助手

基于 LLM 的智能简历筛选应用，支持本地小模型（Ollama）和云端大模型（OpenAI），帮助招聘人员快速解析、评估和匹配候选人简历。

## 功能特性

- 📄 **简历上传与解析** — 支持 PDF、DOCX 格式，AI 自动提取姓名/技能/经验/学历等结构化信息
- 📋 **职位描述管理** — 配置职位描述、关键词筛选、自定义评分标准（必须/重要/加分）
- 🤖 **AI 智能匹配评分** — LLM 驱动的多维度评分（技能/经验/学历），支持评分标准定制
- 🔍 **关键词语义匹配** — 融合文本精确匹配与 LLM 语义理解，避免同义词遗漏
- ✂️ **长简历自动拆分** — Ollama 模式下超长简历自动拆分为多次 LLM 调用，LLM 智能合并结果
- 📊 **评分排序与详情** — 按匹配度自动排序，查看完整匹配分析
- 📱 **响应式设计** — 支持桌面和移动端

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Zustand + React Router |
| 后端 | Python 3.11+ + FastAPI + Pydantic |
| LLM | OpenAI API / Ollama（本地部署） |
| 文档解析 | PyPDF2 + python-docx |

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
LLM_MODEL=qwen3.5:4b
```

**使用 OpenAI（云端模型）：**

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
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
2. **上传简历** — 在「上传简历」页面拖拽或选择文件，支持批量上传
3. **AI 解析** — 上传后自动解析，页面实时显示解析进度和结果
4. **开始匹配** — 在「简历列表」页面选择职位，点击「开始匹配」
5. **查看结果** — 按匹配度排序查看简历，点击详情查看完整分析

## 项目结构

```
.
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── components/          # 通用组件（Navbar, ScoreBadge, SkillTag）
│   │   ├── pages/               # 页面组件
│   │   │   ├── UploadPage.tsx   # 简历上传（轮询解析状态）
│   │   │   ├── JDPage.tsx       # 职位管理（评分标准配置）
│   │   │   ├── ResumesPage.tsx  # 简历列表（匹配/排序）
│   │   │   └── ResumeDetailPage.tsx
│   │   ├── api.ts               # API 调用封装
│   │   ├── store.ts             # Zustand 全局状态
│   │   └── types.ts             # TypeScript 类型定义
│   └── package.json
└── backend/                     # FastAPI 后端
    ├── app/
    │   ├── api/
    │   │   └── routes.py        # API 路由
    │   ├── models/
    │   │   └── schemas.py       # Pydantic 数据模型
    │   └── services/
    │       ├── llm_service.py   # LLM 调用（解析/匹配/合并）
    │       ├── matcher.py       # 匹配调度（批量/异步）
    │       ├── parser.py        # 文件解析（PDF/DOCX）
    │       └── storage.py       # JSON 文件存储
    ├── data/                    # 数据存储目录
    ├── .env.example             # 环境变量示例
    └── requirements.txt
```

## 核心设计

### 小模型优化策略

针对 Ollama 本地小模型（如 qwen3.5:4b）做了以下优化：

| 策略 | 说明 |
|------|------|
| 结构化提示词 + Few-shot | 约束输出为 JSON 格式，通过示例引导模型输出 |
| 提示词压缩 | 移除冗余 Schema 描述，减少 token 消耗 |
| 长简历拆分 | Ollama 模式下，解析超 4000 字 / 匹配超 3000 字自动拆分为两次 LLM 调用 |
| LLM 智能合并 | 拆分后的结果由 LLM 合并，而非简单规则拼接 |
| Provider 感知 | OpenAI 模式不拆分（大模型上下文足够），Ollama 模式按阈值拆分 |

### 关键词语义匹配

关键词匹配采用**双通道融合**策略：

- **文本精确匹配** — 字符串搜索，精确可靠
- **LLM 语义匹配** — 理解同义词和上下文（如简历写"Spring Boot"，关键词"Java"也能命中）
- **合并规则** — 任一方式命中即算匹配，两者都缺失才算缺失

### 评分标准定制

每个职位可配置评分标准，支持三级权重：

- **必须**（红色）— 不满足则该项打极低分
- **重要**（黄色）— 显著影响评分
- **加分**（绿色）— 满足加分，不满足不扣分

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload/batch` | 批量上传简历 |
| GET | `/api/resumes` | 获取简历列表 |
| GET | `/api/resumes/{id}` | 获取简历详情 |
| DELETE | `/api/resumes/{id}` | 删除简历 |
| POST | `/api/jds` | 创建职位 |
| GET | `/api/jds` | 获取职位列表 |
| PUT | `/api/jds/{id}` | 更新职位 |
| DELETE | `/api/jds/{id}` | 删除职位 |
| POST | `/api/match` | 执行匹配 |
| GET | `/api/matches/{jd_id}` | 获取匹配结果 |

完整 API 文档请访问 http://localhost:8000/docs

## License

[Apache License 2.0](LICENSE)
