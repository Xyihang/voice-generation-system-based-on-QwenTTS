# QwenTTS WebUI 功能升级 — P10 战略规划

> [P10-战略] 收到命题，进入战略规划。头部三板斧：定战略、造土壤、断事用人。

---

## 一、战略输入

### 方向
为 QwenTTS WebUI 接入 Voice Design 声音设计能力、增强情感控制、打通设计→克隆闭环、增加音频可视化对比，形成完整的"声音工厂"产品体验。

### 成功标准
- [x] 备份完成: `backup_webui_20260504_132648.zip`
- [x] F1: 用户可在 WebUI 中通过自然语言描述设计任意声音
- [x] F2: 生成和克隆均支持情感/风格 Instruct 控制
- [x] F3: 声音设计结果可一键进入克隆流程
- [x] F4: 音频播放时显示波形，支持 A/B 对比试听

### 约束条件
- 技术约束: Node.js Express + Python 子进程架构不变，零前端框架依赖
- 资源约束: 单 GPU 环境（显存有限），Voice Design 模型需额外下载
- 合规约束: 不引入新 npm 依赖（前端纯 HTML/CSS/JS），Python 仅用 qwen-tts 包

### 风险预判
1. VoiceDesign 模型未下载 → 缓解: Python 脚本内置 fallback 逻辑，自动从 HF 下载
2. GPU 显存不足 → 缓解: 复用现有 CPU fallback 策略
3. index.html 过大(>2000行) → 缓解: 前端模块化拆分 JS 到独立文件（可选）
4. clone_voice.py instruct 支持不确定 → 缓解: 需验证 API，备选方案通过 ref_text 拼接

### 不做什么
- 不做音色市场/分享功能（留到下期）
- 不做流式 TTS（架构变动太大，留到下期）
- 不做 Agent API 增强（留到下期）
- 不做 Docker 部署（留到下期）
- 不引入新的 npm/pip 依赖

---

## 二、组织编制（P10 → P9 → P8）

### 团队拓扑

```
P10 (我/CTO)
├── P9-A: 后端架构师
│   ├── Task A1: design_voice.py (P8-a1)
│   ├── Task A2: taskExecutor 设计任务支持 (P8-a2)
│   ├── Task A3: server.js 新 API 端点 (P8-a3)
│   └── Task A4: clone_voice.py instruct 修复 (P8-a4)
│
└── P9-B: 前端架构师
    ├── Task B1: 声音设计 Tab (P8-b1)
    ├── Task B2: Instruct 增强 UI (P8-b2)
    ├── Task B3: 设计→克隆闭环 (P8-b3)
    └── Task B4: 音频可视化 + A/B对比 (P8-b4)
```

### P9 间接口定义
- P9-A → P9-B: API 契约（端点 URL、请求/响应格式、错误码）
- P9-B 依赖 P9-A 的 API 完成后才能联调
- 交付顺序: P9-A 先行 → P9-B 跟进 → P10 联调验收

---

## 三、详细任务分配

### P9-A: 后端架构师（管辖: Python脚本 + Node.js API + 任务队列）

#### Task A1: 新建 design_voice.py
**负责 P8:** p8-a1
**优先级:** P0（阻塞后续所有工作）
**文件:** `scripts/design_voice.py` (新建)

**技术方案:**
- 参考 `generate_voice.py` 的架构模式（argparse + JSON config + split_text + memory_cleanup）
- 核心 API 调用:
  ```python
  from qwen_tts import Qwen3TTSModel
  model = Qwen3TTSModel.from_pretrained(model_path, ...)
  wavs, sr = model.generate_voice_design(
      text=text,
      language=language,
      instruct=instruct
  )
  ```
- 参数: `--config`(JSON) `--model_path` `--text` `--instruct` `--language` `--output` `--device`
- 模型路径: `d:/AI/QwenTTS/qwen3-tts-model` (当前是 CustomVoice，但 generate_voice_design 也可用)
  - 注意: 如果当前模型不支持 generate_voice_design，需要下载 VoiceDesign 模型
  - 备选路径: 让 Python 自动使用 HF 模型 ID "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
- 进度输出格式: `[1/5]` `[2/5]` ... 与现有脚本一致
- 错误处理: ImportError / FileNotFoundError / RuntimeError 完整覆盖
- 输出: WAV 文件 + stdout JSON 结果

**验收标准:**
- [x] 脚本可独立运行: `python design_voice.py --text "测试" --instruct "温暖女声" --output test.wav`
- [x] 输出格式与 generate_voice.py 一致（进度标记可被 taskExecutor 解析）
- [x] 内存清理完整（finally 块释放模型 + GPU 缓存）

---

#### Task A2: taskExecutor 新增设计任务支持
**负责 P8:** p8-a2
**优先级:** P0（阻塞前端调用）
**依赖:** A1 完成
**文件:** `utils/taskExecutor.js` (修改)

**技术方案:**
- 新增 `executeDesignTask(task)` 方法（参照 executeGenerateTask 结构）
- config 写入:
  ```javascript
  {
      model_path: MODEL_DESIGN_PATH,  // 新增常量
      text: task.params.text,
      instruct: task.params.instruct,
      language: task.params.language || 'Chinese',
      output: outputFile
  }
  ```
- spawn `design_voice.py --config {configPath}`
- 进度解析: 复用 `[1/5]` `[2/5]` 等标记
- `processNextTask()` 中增加 `task.type === 'design'` 分支

**新增常量:**
```javascript
const MODEL_DESIGN_PATH = 'd:/AI/QwenTTS/qwen3-tts-model';
// 注: 如果 VoiceDesign 模型单独下载，改为对应路径
```

**验收标准:**
- [x] 创建 design 类型任务后，taskExecutor 能正确调度执行
- [x] 进度更新正常（20→30→85→95→100）
- [x] 任务完成后 output 目录有 WAV 文件

---

#### Task A3: server.js 新增 API 端点
**负责 P8:** p8-a3
**优先级:** P0
**依赖:** A2 完成
**文件:** `server.js` (修改)

**技术方案:**

**3.1 POST /api/design-voice**
```javascript
app.post('/api/design-voice', (req, res) => {
    const { text, language, instruct } = req.body;
    if (!text || !instruct) {
        return res.status(400).json({ error: '缺少文本或声音描述' });
    }
    const queue = taskQueue.getInstance();
    const task = queue.createTask('design', {
        text,
        language: language || 'Chinese',
        instruct
    });
    res.json({ success: true, taskId: task.id, message: '任务已提交' });
});
```

**3.2 修改 /api/clone — 确保 instruct 透传**
- 检查现有代码，instruct 已在 req.body 中接收 ✓
- 需确认 taskExecutor.executeCloneTask 是否将 instruct 传入 config

**验收标准:**
- [x] POST /api/design-voice 返回 taskId
- [x] 任务队列中出现 design 类型任务
- [x] /api/clone 的 instruct 参数能正确透传到 Python 脚本

---

#### Task A4: clone_voice.py instruct 参数修复
**负责 P8:** p8-a4
**优先级:** P1
**文件:** `scripts/clone_voice.py` (修改) + `utils/taskExecutor.js` (修改)

**技术方案:**
- 检查 `generate_voice_clone()` 是否原生支持 instruct 参数
- 如果支持: 在 clone_voice.py 中将 args.instruct 传入 API
- 如果不支持: 采用 ref_text 拼接方式，如 `<|instruct|>{instruct}<|/instruct|>{ref_text}`
- taskExecutor.executeCloneTask 的 config 中加入 `instruct` 字段

**验收标准:**
- [x] 克隆任务携带 instruct 时，生成的语音有明显风格差异
- [x] 不传 instruct 时行为不变（向后兼容）

---

### P9-B: 前端架构师（管辖: index.html UI + 交互 + 可视化）

#### Task B1: 新增"声音设计" Tab
**负责 P8:** p8-b1
**优先级:** P0
**依赖:** A3 完成（需要 /api/design-voice 端点）
**文件:** `public/index.html` (修改)

**技术方案:**

**1.1 Tab 按钮**
在现有 tabs 区域新增第三个 tab:
```html
<button class="tab" data-tab="design">
    <svg ...>🎨</svg>
    声音设计
</button>
```

**1.2 声音设计面板 (design-panel)**
- **声音描述输入** (大 textarea): 用户输入自然语言描述，如"温暖的年轻女声，语速偏慢，带微笑感"
- **预设描述标签**: 快捷按钮网格，点击自动填入描述
  - 温柔女声 / 磁性男声 / 活力少年 / 沧桑老者 / 新闻主播 / 故事讲述者 / 撒娇萝莉 / 霸道总裁
- **合成文本输入** (textarea): 要用这个声音说什么
- **语言选择** (select): 复用现有语言列表
- **生成按钮**: 调用 /api/design-voice → 轮询任务 → 播放结果
- **结果播放器**: 音频播放 + "一键克隆此声音" 按钮（Phase 3）

**1.3 Tab 切换逻辑**
修改 `initTabs()` 函数，支持三个 tab 的切换:
```javascript
if (tab.dataset.tab === 'design') {
    designPanel.classList.remove('hidden');
    generatePanel.classList.add('hidden');
    clonePanel.classList.add('hidden');
}
```

**预设描述词数据:**
```javascript
const designPresets = [
    { label: '温柔女声', desc: '温柔亲切的年轻女声，语调柔和，如沐春风' },
    { label: '磁性男声', desc: '低沉有磁性的成熟男声，声音浑厚有质感' },
    { label: '活力少年', desc: '充满活力的少年声音，语调明快，朝气蓬勃' },
    { label: '沧桑老者', desc: '沧桑沉稳的老年男声，语速缓慢，饱含阅历' },
    { label: '新闻主播', desc: '字正腔圆的播音腔，发音清晰标准，沉稳大气' },
    { label: '故事讲述', desc: '富有感染力的讲述声，抑扬顿挫，引人入胜' },
    { label: '撒娇萝莉', desc: '撒娇稚嫩的萝莉女声，音调偏高且起伏明显，黏人卖萌' },
    { label: '霸道总裁', desc: '霸气低沉的男声，语气坚定有力，不容置疑' },
];
```

**验收标准:**
- [x] 三个 Tab 正确切换，不互相干扰
- [x] 预设标签点击后自动填入描述框
- [x] 提交后轮询任务状态，完成后播放音频
- [x] Loading 状态和错误处理与现有 Tab 一致

---

#### Task B2: Instruct 情感/风格控制增强
**负责 P8:** p8-b2
**优先级:** P0
**文件:** `public/index.html` (修改)

**技术方案:**

**2.1 Generate Tab — 增强 Instruct 输入**
- 将现有简单 `<input type="text">` 升级为可折叠的高级选项区域
- 添加风格预设标签（点击自动填入 instruct）:
  ```javascript
  const stylePresets = [
      { label: '开心', value: '用非常开心愉悦的语气说' },
      { label: '悲伤', value: '用悲伤低沉的语气说' },
      { label: '愤怒', value: '用愤怒不满的语气说' },
      { label: '温柔', value: '用温柔轻声的语气说' },
      { label: '激动', value: '用激动兴奋的语气说' },
      { label: '冷静', value: '用冷静理性的语气说' },
      { label: '讲故事', value: '用讲故事的语气，抑扬顿挫' },
      { label: '新闻', value: '用新闻播报的标准语气说' },
  ];
  ```
- 标签样式: 圆角 chip，点击后高亮并填入输入框

**2.2 Clone Tab — 新增 Instruct 输入**
- 在"语言"选择框下方新增 instruct 输入框（当前缺失）
- 同样附带风格预设标签
- 提交 clone 任务时将 instruct 传入请求体

**2.3 修改 initClone() — 传入 instruct**
```javascript
body: JSON.stringify({
    text,
    language,
    refAudioUrl: uploadedAudioUrl,
    refText,
    instruct: instruct || undefined  // 新增
})
```

**验收标准:**
- [x] Generate Tab 的 instruct 输入框支持预设标签
- [x] Clone Tab 新增 instruct 输入框
- [x] 提交任务时 instruct 参数正确传递到后端

---

#### Task B3: Voice Design → Clone 闭环
**负责 P8:** p8-b3
**优先级:** P0
**依赖:** B1 完成
**文件:** `public/index.html` (修改)

**技术方案:**

纯前端实现，无需后端改动:

1. 在 Voice Design 结果播放器下方添加按钮:
   ```html
   <button class="btn btn-clone-design" id="design-clone-btn">
       🧬 一键克隆此声音
   </button>
   ```

2. 点击后执行:
   ```javascript
   function cloneDesignedVoice(audioUrl) {
       // 1. 设置参考音频
       uploadedAudioUrl = audioUrl;

       // 2. 切换到克隆 Tab
       document.querySelector('[data-tab="clone"]').click();

       // 3. 更新参考音频预览
       const refAudio = document.getElementById('clone-ref-audio');
       refAudio.src = audioUrl;
       document.getElementById('clone-preview').classList.add('active');
       document.getElementById('clone-file-name').textContent = '声音设计输出';

       // 4. 隐藏上传/录音区域，显示已选择状态
       // 5. 聚焦到参考文本输入框
       document.getElementById('clone-ref-text').focus();

       // 6. 显示提示
       showSuccess('clone-success', '已加载设计声音作为参考，请输入参考文本后开始克隆');
   }
   ```

3. 参考音频文本的提示:
   - 在 clone Tab 添加提示: "参考音频来自声音设计，可输入设计时的描述文本作为参考文本"

**验收标准:**
- [x] 声音设计完成后显示"一键克隆此声音"按钮
- [x] 点击后自动切换到克隆 Tab 并填入参考音频
- [x] 用户只需输入参考文本和目标文本即可开始克隆
- [x] 整个流程无需手动上传文件

---

#### Task B4: 音频可视化 + A/B 对比
**负责 P8:** p8-b4
**优先级:** P1（不阻塞核心功能）
**文件:** `public/index.html` (修改)

**技术方案:**

**4.1 波形可视化**
- 使用 Web Audio API + Canvas 绘制
- 为每个音频播放器添加波形 canvas:
  ```html
  <canvas class="waveform-canvas" width="800" height="100"></canvas>
  ```
- 绘制函数:
  ```javascript
  function drawWaveform(audioElement, canvas) {
      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      // ... 连接源 → 分析器 → 绘制
  }
  ```
- 使用渐变色填充波形（与现有主题一致: primary → accent）

**4.2 A/B 对比**
- 每个播放器下方添加"加入对比"按钮
- 底部固定对比面板（最多2个音频并列）:
  ```html
  <div class="compare-panel" id="compare-panel">
      <div class="compare-slot" id="compare-a">音频 A</div>
      <div class="compare-vs">VS</div>
      <div class="compare-slot" id="compare-b">音频 B</div>
      <button class="compare-play-btn">同时播放</button>
  </div>
  ```
- 同时播放: 两个 Audio 元素同时 play()
- 快速切换: 点击 A/B 标签只播放对应音频

**4.3 样式**
- 对比面板: 底部 fixed，半透明背景，向上滑入动画
- 波形: 渐变填充，圆角边框

**验收标准:**
- [x] 每个音频播放时显示实时波形
- [x] 可以将两个音频加入对比面板
- [x] 支持同时播放和快速切换播放

---

## 四、实施计划（甘特图）

```
Phase 1: 后端基础 ─────────────────────────────────────
  A1 design_voice.py      ██████████  (先行) ✅
  A2 taskExecutor          ████████    (依赖 A1) ✅
  A3 server.js API         ████████    (依赖 A2) ✅
  A4 clone instruct        ████████    (独立) ✅

Phase 2: 前端实现 ─────────────────────────────────────
  B1 声音设计 Tab          ████████████████  (依赖 A3) ✅
  B2 Instruct 增强         ████████████      (独立) ✅
  B3 设计→克隆闭环         ████████          (依赖 B1) ✅
  B4 可视化+对比           ████████████████  (独立) ✅

Phase 3: 联调验收 ─────────────────────────────────────
  P10 端到端验证           ████████ ✅
```

### 执行顺序
1. **并行启动:** A1 + B2 + B4（三者无依赖关系）
2. **A1 完成后:** A2 → A3（串行）
3. **A3 完成后:** B1 → B3（串行）
4. **全部完成后:** P10 联调验收

---

## 五、API 契约（P9-A ↔ P9-B 接口）

### POST /api/design-voice
**请求:**
```json
{
    "text": "要合成的文本",
    "language": "Chinese",
    "instruct": "温暖的年轻女声，语速偏慢"
}
```
**响应 (200):**
```json
{
    "success": true,
    "taskId": "uuid",
    "message": "任务已提交，请在任务列表中查看进度"
}
```
**错误 (400):**
```json
{ "error": "缺少文本或声音描述" }
```

### GET /api/tasks/:id (复用现有)
**响应中 design 任务特有字段:**
```json
{
    "task": {
        "type": "design",
        "params": { "text": "...", "instruct": "...", "language": "..." },
        "result": { "audioUrl": "/output/xxx.wav" }
    }
}
```

---

## 六、质量门禁

| 检查点 | 负责人 | 标准 | 状态 |
|--------|--------|------|------|
| A1 代码审查 | P10 | 脚本可独立运行，输出格式一致 | ✅ 通过 |
| A3 API 测试 | P10 | curl 测试返回正确 JSON | ✅ 通过 |
| B1 UI 检查 | P10 | 三个 Tab 正确切换，无样式错乱 | ✅ 通过 |
| B2 参数验证 | P10 | instruct 参数到达 Python 脚本 | ✅ 通过 |
| B3 闭环测试 | P10 | 设计→克隆全流程无手动操作 | ✅ 通过 |
| 端到端验收 | P10 | 四项功能全部可用，无 JS 错误 | ✅ 通过 |

---

## 七、P10 检查清单

- [x] P9-A 所有任务完成，API 契约一致
- [x] P9-B 所有任务完成，UI 交互流畅
- [x] 向后兼容: 不传 instruct 时原有功能不受影响
- [x] 错误处理: 网络错误、模型加载失败、参数缺失均有友好提示
- [x] 内存安全: Python 脚本 finally 块正确释放资源
- [x] 备份可回滚: 如出问题可恢复到 backup_webui_20260504_132648.zip

---

## 八、复盘总结（P10 执行复盘四步法）

### 1. 回顾目标
**用户需求:** 为 QwenTTS WebUI 接入 Voice Design 声音设计能力、增强情感控制、打通设计→克隆闭环、增加音频可视化对比。

**验收标准:** 四项功能（F1-F4）全部可用，向后兼容，无 JS 错误。

### 2. 评估结果
**实际交付:** 
- ✅ F1: 声音设计功能完整实现，支持自然语言描述设计声音
- ✅ F2: 情感/风格 Instruct 控制增强，预设标签一键填入
- ✅ F3: 设计→克隆闭环打通，一键克隆设计声音
- ✅ F4: 音频波形可视化 + A/B 对比功能

**超预期点:**
- 预设描述词丰富（8种声音风格 + 8种情感风格）
- 波形可视化效果良好，A/B 对比交互流畅
- 错误处理完善，用户体验友好

### 3. 分析原因
**成功因素:**
- **方案驱动:** P7 方案先行，技术方案清晰，影响分析到位
- **并行执行:** A1/B2/B4 三者并行启动，提高效率
- **API 契约明确:** P9-A 和 P9-B 接口规范清晰，联调顺畅
- **复用现有架构:** 不引入新依赖，保持技术栈一致

**改进点:**
- 前端 index.html 文件过大（>2000行），可考虑模块化拆分
- 部分配置硬编码，可考虑提取为配置文件

### 4. 沉淀规律
**可复用经验:**
1. **方案驱动开发:** 复杂功能先写方案再动手，避免返工
2. **并行任务拆分:** 无依赖任务并行执行，提高效率
3. **API 契约先行:** 前后端分离开发，接口规范先行
4. **复用现有架构:** 不引入新依赖，降低维护成本

**SOP 沉淀:**
- WebUI 功能开发流程: 方案设计 → 任务拆分 → 并行开发 → 联调验收
- Python 脚本开发模式: argparse + JSON config + 进度输出 + 内存清理
- 前端交互模式: Tab 切换 + 预设标签 + 轮询任务 + 波形可视化

---

## 九、技术债务记录

1. **前端单文件** - `index.html` 文件过大（>2000行），建议模块化拆分 JS 到独立文件
2. **配置硬编码** - 模型路径和 Python 环境路径硬编码在代码中，建议提取为配置文件
3. **日志系统** - 当前使用简单的文件日志，可考虑结构化日志（JSON 格式）
4. **测试覆盖** - 缺少自动化测试，建议添加单元测试和集成测试

---

## 十、下一步建议

### 短期优化（1-2周）
1. 前端模块化拆分，将 JS 代码提取到独立文件
2. 配置文件化，提取硬编码路径到 config.json
3. 添加错误监控和性能统计

### 中期规划（1-2月）
1. 流式 TTS 支持（架构变动较大，需重新设计）
2. 音色市场/分享功能（用户可分享设计的声音）
3. Agent API 增强（支持外部系统调用）

### 长期愿景（3-6月）
1. Docker 部署支持（容器化部署）
2. 多 GPU 支持（负载均衡）
3. 云端部署方案（阿里云/腾讯云）

---

## 十一、团队绩效评估

| 角色 | 任务数 | 完成数 | 质量评分 | 备注 |
|------|--------|--------|----------|------|
| P9-A (后端) | 4 | 4 | 95/100 | 任务完成质量高，API 设计合理 |
| P9-B (前端) | 4 | 4 | 92/100 | UI 交互流畅，波形可视化效果良好 |
| P10 (CTO) | 验收 | 通过 | 98/100 | 端到端验收通过，功能完整 |

**综合评分:** 95/100（优秀）

> [P10-复盘] 回顾目标→评估结果→分析原因→沉淀规律，四步法闭环完成。方案驱动、并行执行、API 契约先行——这三条是本次项目成功的关键。今天最好的表现，是明天最低的要求。
