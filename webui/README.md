# Qwen3-TTS WebUI

<p align="center">
  <img src="https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/qwen3_tts_introduction.png" width="70%"/>
</p>

> ⚠️ **本项目由 Vibe Coding 方式编写，介意请离开。**
>
> 由 **MiMo-v2.5-pro**、**Kimi-k2.5 / k2.6** 和 **GLM-5** 协同编写。

***

## 简介

Qwen3-TTS WebUI 是一个基于 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) 的本地语音合成工具，提供直观的 Web 界面，支持：

- 🎤 **语音生成** — 输入文本，选择音色和语言，生成自然语音
- 🎨 **音色设计** — 用自然语言描述想要的音色（如"温柔的年轻女声"），AI 自动生成
- 🔊 **声音克隆** — 上传参考音频，克隆音色并合成新文本
- 📝 **音频转文字** — 基于 Whisper 的语音识别，支持 10 种语言转录
- 📊 **A/B 对比** — 将不同生成结果并排对比试听
- 🎵 **波形可视化** — 实时波形图播放器，支持拖动跳转
- 📋 **任务队列** — 异步执行，支持并发任务管理

## 环境要求

| 依赖          | 版本要求                 | 说明                |
| ----------- | -------------------- | ----------------- |
| **操作系统**    | Windows 10/11        | 目前仅测试了 Windows 环境 |
| **GPU**     | NVIDIA，8GB+ 显存       | 推荐 RTX 3060 及以上   |
| **CUDA**    | 12.x                 | 需与 PyTorch 版本匹配   |
| **Python**  | 3.12                 | 通过 Conda 管理       |
| **Node.js** | 22+                  | LTS 版本即可          |
| **Conda**   | Miniconda / Anaconda | 用于管理 Python 环境    |

***

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/<your-username>/QwenTTS.git
cd QwenTTS/webui
```

### 2. 创建 Python 环境

```bash
conda create -n qwen3-tts python=3.12 -y
conda activate qwen3-tts
pip install -U qwen-tts
```

如果你在中国大陆，建议使用国内镜像加速：

```bash
pip install -U qwen-tts -i https://mirrors.aliyun.com/pypi/simple/
```

### 3. 下载模型

本项目需要两个模型，请按需下载到项目根目录：

#### 方式一：ModelScope（推荐国内用户）

```bash
pip install -U modelscope

# 语音生成 / 声音克隆 基础模型（必需）
modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-Base --local_dir ./qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base

# 音色设计模型（如需使用音色设计功能）
modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign --local_dir ./qwen3-tts-model/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

#### 方式二：Hugging Face

```bash
pip install -U "huggingface_hub[cli]"

# 语音生成 / 声音克隆 基础模型（必需）
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base --local-dir ./qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base

# 音色设计模型（如需使用音色设计功能）
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign --local-dir ./qwen3-tts-model/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

#### 模型目录结构

下载完成后，目录结构应如下：

```
QwenTTS/
├── qwen3-tts-base-model/          # 语音生成 / 声音克隆模型
│   └── Qwen/
│       └── Qwen3-TTS-12Hz-1.7B-Base/
│           ├── speech_tokenizer/   # 语音编码器
│           │   ├── config.json
│           │   ├── configuration.json
│           │   ├── model.safetensors
│           │   └── preprocessor_config.json
│           ├── config.json
│           ├── generation_config.json
│           ├── model.safetensors
│           ├── tokenizer_config.json
│           ├── vocab.json
│           └── merges.txt
│
├── qwen3-tts-model/               # 音色设计模型
│   └── Qwen3-TTS-12Hz-1.7B-VoiceDesign/
│       ├── speech_tokenizer/
│       ├── config.json
│       ├── model.safetensors
│       └── ...
│
└── webui/                         # 本项目（WebUI）
    ├── server.js
    ├── package.json
    ├── public/
    ├── scripts/
    └── utils/
```

### 4. 修改模型路径

打开 `webui/server.js`，找到以下两行，修改为你的实际模型路径：

```javascript
const MODEL_BASE_PATH = 'D:/your/path/to/qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base';
const VOICE_DESIGN_MODEL_PATH = 'D:/your/path/to/qwen3-tts-model/Qwen3-TTS-12Hz-1.7B-VoiceDesign';
```

同样修改 Python 脚本中的默认路径（如需要）：

- `webui/scripts/generate_voice.py` → `DEFAULT_MODEL_PATH`
- `webui/scripts/clone_voice.py` → `DEFAULT_MODEL_PATH`
- `webui/scripts/design_voice.py` → `DEFAULT_MODEL_PATH`

### 5. 修改 Python 路径

打开 `webui/utils/taskExecutor.js` 和 `webui/server.js`，找到 `CONDA_PYTHON` 变量，修改为你的 Conda 环境 Python 路径：

```javascript
const CONDA_PYTHON = 'C:/Users/<你的用户名>/miniconda3/envs/qwen3-tts/python.exe';
```

### 6. 安装 Node.js 依赖

```bash
cd webui
npm install
```

### 7. 启动

```bash
npm start
```

或使用双击启动脚本：

```bash
start.bat
```

启动后浏览器访问：**<https://localhost:3000>**

> 首次访问会提示证书不安全（自签名证书），点击"高级" → "继续访问"即可。

***

## 项目结构

```
webui/
├── server.js                 # Express 服务器（HTTPS + API 路由）
├── package.json              # Node.js 依赖配置
├── start.bat                 # Windows 一键启动脚本
├── plan.md                   # 开发计划文档
├── ROLE.md                   # 团队角色分工矩阵
│
├── public/                   # 前端静态文件
│   ├── index.html            # 主界面（语音生成 / 音色设计 / 声音克隆）
│   └── tasks.html            # 任务队列管理界面
│
├── scripts/                  # Python 脚本
│   ├── generate_voice.py     # 语音生成
│   ├── clone_voice.py        # 声音克隆
│   ├── design_voice.py       # 音色设计
│   └── debug_tts.py          # 调试工具
│
├── utils/                    # Node.js 工具模块
│   ├── taskExecutor.js       # 任务执行器（进程管理 + 输出解析）
│   └── taskQueue.js          # 内存任务队列（单例）
│
└── keys/                     # SSL 证书（自动生成）
    ├── cert.pem
    └── key.pem
```

***

## 功能说明

### 🎤 语音生成

输入文本 → 选择音色（18种预设）→ 选择语言 → 生成语音

支持 10 种语言：中文、英文、日文、韩文、德语、法语、俄语、葡萄牙语、西班牙语、意大利语

### 🎨 音色设计

用自然语言描述想要的音色，例如：

- "温柔的年轻女声，语速适中"
- "低沉磁性的男声，带有轻微的回声效果"
- "活泼的少年音，充满朝气"

AI 会根据描述自动生成对应的音色，并支持一键克隆到声音克隆模块。

### 🔊 声音克隆

上传或录制 3-10 秒的参考音频 → 输入参考文本 → 输入要合成的文本 → 克隆音色

支持 instruct 模式精细控制音色风格。

### 📊 A/B 对比

将不同生成结果加入对比，支持：

- 最多 2 个音频并排对比
- 同时播放
- 跨页面同步（任务列表 → 主页）

### 🎵 波形播放器

- 实时波形图渲染
- 点击跳转播放位置
- 拖动调整进度
- 播放时间显示

### 📋 任务队列

- 异步任务执行
- 实时进度追踪
- 任务持久化（重启后自动恢复）
- 活跃任务自动刷新

***

## API 接口

| 方法     | 路径                  | 说明      |
| ------ | ------------------- | ------- |
| POST   | `/api/generate`     | 语音生成    |
| POST   | `/api/clone`        | 声音克隆    |
| POST   | `/api/design-voice` | 音色设计    |
| GET    | `/api/tasks`        | 获取所有任务  |
| GET    | `/api/tasks/:id`    | 获取单个任务  |
| DELETE | `/api/tasks/:id`    | 删除任务    |
| GET    | `/output/:filename` | 下载生成的音频 |

***

## 常见问题

### Q: 首次生成很慢？

A: 首次需要加载模型到 GPU，约 30-60 秒。后续生成会复用已加载的模型，速度约 30 秒/段。

### Q: 显存不足 (OOM)？

A: 系统会在生成完成后自动清理 GPU 显存。如果仍然 OOM，可以：

- 减少输入文本长度
- 重启服务释放显存
- 使用显存更大的 GPU

### Q: 任务一直卡在"运行中"？

A: 请检查终端日志。如果显示 `[CLEANUP] Memory released` 后仍卡住，可能是 Python 输出缓冲区问题。本项目已通过 `-u` 参数和 `sys.stdout.flush()` 修复此问题。

### Q: 证书警告怎么办？

A: 本项目使用自签名 HTTPS 证书，首次访问时浏览器会提示不安全。点击"高级" → "继续访问"即可。证书会在首次启动时自动生成。

***

## 致谢

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) — 通义千问语音合成模型
- [Hugging Face](https://huggingface.co/Qwen) — 模型托管
- [ModelScope](https://modelscope.cn/models/Qwen) — 国内模型下载

***

## 开发声明

Made By Xyihang

> ⚠️ **本项目由 Vibe Coding 方式编写，介意请离开。**
>
> 本项目的代码由以下 AI 模型协同编写：
>
> - **MiMo-v2.5-pro** (小米)
> - **Kimi-k2.5 / k2.6** (月之暗面)
> - **GLM-5** (智谱)
>
> 人类负责提出需求、审查代码和最终决策，AI 负责具体实现。
>
> 代码质量、架构设计和功能实现均由 AI 完成，可能存在非人类思维方式的实现路径。
> 如果你对 AI 生成的代码有顾虑，请谨慎使用。

***

## 许可证

本项目基于 Apache 2.0 许可证开源。模型使用请遵循 [Qwen3-TTS 许可协议](https://github.com/QwenLM/Qwen3-TTS)。
