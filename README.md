# Qwen3-TTS 语音合成系统 · 部署教程

基于 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) 的本地语音合成 WebUI,支持语音生成、音色设计、声音克隆与音频转文字。

本文只讲**从零到跑起来**的完整步骤。所有路径常量与命令均以仓库内实际代码为准。

---

## 一、环境要求

| 依赖 | 版本要求 | 说明 |
| --- | --- | --- |
| 操作系统 | Windows 10 / 11 | 目前仅在 Windows 上验证过 |
| GPU | NVIDIA,8 GB 显存以上 | 推荐 RTX 3060 及以上 |
| CUDA | 12.x | 需与 PyTorch 版本匹配 |
| Python | 3.12 | 用 Conda 管理 |
| Node.js | 22 及以上 | LTS 版本即可 |
| Conda | Miniconda 或 Anaconda | 用于管理 Python 环境 |

没有 NVIDIA 显卡无法运行:模型推理走 CUDA,纯 CPU 环境不适用。

---

## 二、部署步骤

### 步骤 1:获取代码

```bash
git clone https://github.com/Xyihang/voice-generation-system-based-on-QwenTTS.git
cd voice-generation-system-based-on-QwenTTS
```

克隆出来的目录名是仓库名本身(`voice-generation-system-based-on-QwenTTS`),后续所有相对路径都以它作为项目根目录。

### 步骤 2:创建 Python 环境

```bash
conda create -n qwen3-tts python=3.12 -y
conda activate qwen3-tts
pip install -U qwen-tts
```

国内网络建议走镜像加速:

```bash
pip install -U qwen-tts -i https://mirrors.aliyun.com/pypi/simple/
```

`qwen-tts` 会一并带入 PyTorch 等依赖。若需要指定 CUDA 版本,再单独安装对应的 PyTorch。

### 步骤 3:下载模型

需要两个模型,下载到**项目根目录**(与 `webui` 同级)。

**ModelScope(国内推荐)**

```bash
pip install -U modelscope

# 语音生成 / 声音克隆 基础模型(必需)
modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-Base --local_dir ./qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base

# 音色设计模型(用音色设计功能时必需)
modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign --local_dir ./qwen3-tts-model/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

**Hugging Face**

```bash
pip install -U "huggingface_hub[cli]"

huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base --local-dir ./qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign --local-dir ./qwen3-tts-model/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

国内访问 Hugging Face 不稳定时,先设镜像再下载:

```bash
set HF_ENDPOINT=https://hf-mirror.com
```

下载完成后,项目根目录应长这样:

```
voice-generation-system-based-on-QwenTTS/
├── qwen3-tts-base-model/
│   └── Qwen/
│       └── Qwen3-TTS-12Hz-1.7B-Base/
│           ├── speech_tokenizer/
│           ├── config.json
│           ├── generation_config.json
│           ├── model.safetensors
│           ├── tokenizer_config.json
│           ├── vocab.json
│           └── merges.txt
├── qwen3-tts-model/
│   └── Qwen3-TTS-12Hz-1.7B-VoiceDesign/
└── webui/
```

### 步骤 4(可选):下载 Whisper 模型

只有「音频转文字」功能需要。模型放在 `webui/whisper_models/large-v3-turbo.pt`。

首次使用该功能时会自动从 Hugging Face 下载并转换格式,耗时约 5–10 分钟。也可以手动下载:

```bash
conda activate qwen3-tts
pip install openai-whisper huggingface_hub

python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='openai/whisper-large-v3-turbo', filename='model.safetensors', local_dir='./webui/whisper_models')"
```

国内同样可先设 `set HF_ENDPOINT=https://hf-mirror.com`。

### 步骤 5:修改路径常量(最关键的一步)

仓库里的路径常量是开发机上的绝对路径,**不改则无法启动推理**。按下表逐个替换成你自己的实际路径。

| 文件 | 常量 | 应改为 |
| --- | --- | --- |
| `webui/server.js` | `MODEL_BASE_PATH` | 基础模型目录,如 `d:/AI/QwenTTS/qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base` |
| `webui/server.js` | `MODEL_VOICE_PATH` | 音色模型父目录,如 `d:/AI/QwenTTS/qwen3-tts-model` |
| `webui/server.js` | `MODEL_DESIGN_PATH` | 音色设计模型目录 |
| `webui/server.js` | `CONDA_PYTHON` | Conda 环境的 python.exe 全路径 |
| `webui/utils/taskExecutor.js` | `CONDA_PYTHON` | 同上,必须保持一致 |

一共 5 个常量,改完即可。

**`webui/scripts/` 下的 Python 脚本不需要改。** 它们的模型路径由 `server.js` 通过命令行参数 `--model_path` 传入(脚本内是 `parser.add_argument('--model_path', type=str)`,没有默认值,也没有硬编码路径),所以路径只需要在 `server.js` 里配对。

`CONDA_PYTHON` 一般长这样:

```javascript
const CONDA_PYTHON = 'C:/Users/<你的用户名>/miniconda3/envs/qwen3-tts/python.exe';
```

自己不确定路径时,在已激活环境的终端里执行 `where python` 取得。

路径用正斜杠 `/` 或转义的反斜杠 `\\`,不要直接写单个 `\`。

### 步骤 6:安装 Node.js 依赖

```bash
cd webui
npm install
```

### 步骤 7:启动

```bash
cd webui
npm start
```

或者直接双击 `webui/start.bat`。启动脚本会自动检查 Node.js 环境,并在 `node_modules` 不存在时自动执行 `npm install`。

服务端口在 `webui/server.js` 中固定为 **3000**。

启动后访问:

```
https://localhost:3000
```

首次访问会提示证书不安全(自签名证书,首次启动自动生成),点「高级」→「继续访问」即可。

若你的环境未能成功生成证书,可尝试 `http://localhost:3000`。

---

## 三、首次使用须知

- **首次生成会明显慢**:模型要加载到显存,约 30–60 秒。之后复用已加载的模型,单段约 30 秒。
- **显存不足(OOM)**:生成完成后系统会自动清理显存。仍然不够时,缩短输入文本、重启服务,或换显存更大的显卡。
- **证书警告**:属正常现象,自签名证书无法被浏览器自动信任。

---

## 四、常见问题

**Q:启动后访问打不开页面?**

按顺序排查:确认 `npm start` 的终端没有报错;确认端口 3000 未被占用;确认访问的是 `https://` 而不是 `http://`。

**Q:点了生成,任务一直停在「运行中」?**

看终端日志。如果 Python 进程直接报错,多数是 `CONDA_PYTHON` 路径不对,或者 `qwen-tts` 没装进那个环境。可用 `scripts/debug_tts.py` 单独跑一次定位问题。

**Q:报模型加载失败 / 找不到 safetensors?**

`MODEL_BASE_PATH` 等常量与实际解压目录不一致。常量要指向**包含 `config.json` 的那一层**,不是它的上一层。

**Q:音色设计功能报错,但语音生成正常?**

音色设计用的是另一个模型(`Qwen3-TTS-12Hz-1.7B-VoiceDesign`),需要单独下载,并单独配置 `MODEL_DESIGN_PATH`。

**Q:音频转文字一直没反应?**

Whisper 模型还没下好,或者没装 `openai-whisper`。检查 `webui/whisper_models/large-v3-turbo.pt` 是否存在。

---

## 五、目录速览

```
webui/
├── server.js              Express 服务器(HTTPS + API 路由),端口 3000
├── package.json           Node 依赖
├── start.bat              Windows 一键启动
├── public/                前端页面(index.html / tasks.html)
├── scripts/               Python 推理脚本
│   ├── generate_voice.py  语音生成
│   ├── clone_voice.py     声音克隆
│   ├── design_voice.py    音色设计
│   ├── transcribe.py      音频转文字
│   └── debug_tts.py       调试
├── utils/
│   ├── taskExecutor.js    任务执行器(进程管理)
│   └── taskQueue.js       内存任务队列
└── keys/                  SSL 证书(首次启动自动生成)
```

---

## 六、接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/generate` | 语音生成 |
| POST | `/api/clone` | 声音克隆 |
| POST | `/api/design-voice` | 音色设计 |
| POST | `/api/transcribe` | 音频转文字 |
| GET | `/api/tasks` | 获取所有任务 |
| GET | `/api/tasks/:id` | 获取单个任务 |
| GET | `/api/tasks/:id/text` | 获取转录文本 |
| DELETE | `/api/tasks/:id` | 删除任务 |
| GET | `/output/:filename` | 下载生成的音频或文本 |

---

## 七、致谢

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) — 通义千问语音合成模型
- [Hugging Face](https://huggingface.co/Qwen) — 模型托管
- [ModelScope](https://modelscope.cn/models/Qwen) — 国内模型下载

---

Made By Xyihang
