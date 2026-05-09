const express = require('express');
const multer = require('multer');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { v4: uuidv4 } = require('uuid');
const taskQueue = require('./utils/taskQueue');
const taskExecutor = require('./utils/taskExecutor');

const LOG_DIR = path.join(__dirname, 'logs');
const LOG_FILE = path.join(LOG_DIR, `server_${new Date().toISOString().slice(0,10)}.log`);

if (!fs.existsSync(LOG_DIR)) {
    fs.mkdirSync(LOG_DIR, { recursive: true });
}

const logStream = fs.createWriteStream(LOG_FILE, { flags: 'a' });

const originalConsoleLog = console.log;
const originalConsoleError = console.error;

function log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logLine = `[${timestamp}] [${level}] ${message}`;
    originalConsoleLog(logLine);
    logStream.write(logLine + '\n');
}

console.log = (...args) => {
    const message = args.map(a => typeof a === 'object' ? JSON.stringify(a) : a).join(' ');
    log(message, 'INFO');
};

console.error = (...args) => {
    const message = args.map(a => typeof a === 'object' ? JSON.stringify(a) : a).join(' ');
    log(message, 'ERROR');
};

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());
app.use(express.static('public'));
app.use('/uploads', express.static('uploads'));
app.use('/output', express.static('output'));

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, 'uploads/');
    },
    filename: (req, file, cb) => {
        const ext = path.extname(file.originalname);
        cb(null, `${uuidv4()}${ext}`);
    }
});

const upload = multer({
    storage,
    limits: { fileSize: 50 * 1024 * 1024 },
    fileFilter: (req, file, cb) => {
        const allowedTypes = ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.webm'];
        const ext = path.extname(file.originalname).toLowerCase();
        if (allowedTypes.includes(ext)) {
            cb(null, true);
        } else {
            cb(new Error('不支持的音频格式'));
        }
    }
});

const MODEL_BASE_PATH = 'd:/AI/QwenTTS/qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base';
const MODEL_VOICE_PATH = 'd:/AI/QwenTTS/qwen3-tts-model';
const MODEL_DESIGN_PATH = 'd:/AI/QwenTTS/qwen3-tts-voice-design-model';
const CONDA_PYTHON = 'C:/Users/xiyih/miniconda3/envs/qwen3-tts/python.exe';

function runPythonScript(scriptName, args) {
    return new Promise((resolve, reject) => {
        const scriptPath = path.join(__dirname, 'scripts', scriptName);
        const env = {
            ...process.env,
            PYTHONIOENCODING: 'utf-8',
            PYTHONUTF8: '1',
            LANG: 'en_US.UTF-8',
            PYTORCH_CUDA_ALLOC_CONF: 'expandable_segments:True'
        };
        const pythonProcess = spawn(CONDA_PYTHON, [scriptPath, ...args], {
            cwd: __dirname,
            env: env,
            stdio: ['pipe', 'pipe', 'pipe']
        });

        let stdout = '';
        let stderr = '';

        pythonProcess.stdout.on('data', (data) => {
            const output = data.toString();
            stdout += output;
            console.log(`[Python] ${output.trim()}`);
        });

        pythonProcess.stderr.on('data', (data) => {
            stderr += data.toString();
            console.error(`[Python Error] ${data.toString().trim()}`);
        });

        pythonProcess.on('close', (code) => {
            if (code === 0) {
                resolve(stdout.trim());
            } else {
                reject(new Error(`Python script exited with code ${code}: ${stderr}`));
            }
        });

        pythonProcess.on('error', (err) => {
            reject(err);
        });
    });
}

app.post('/api/generate', (req, res) => {
    const { text, language, speaker, instruct } = req.body;

    if (!text) {
        return res.status(400).json({ error: '缺少文本内容' });
    }

    const queue = taskQueue.getInstance();
    const task = queue.createTask('generate', {
        text,
        language: language || 'Chinese',
        speaker: speaker || 'Vivian',
        instruct: instruct || null
    });

    console.log(`[API] 语音生成任务已创建：${task.id}`);

    res.json({
        success: true,
        taskId: task.id,
        message: '任务已提交，请在任务列表中查看进度'
    });
});

app.post('/api/clone', (req, res) => {
    const { text, language, refAudioUrl, refText, instruct } = req.body;

    if (!text || !refAudioUrl || !refText) {
        return res.status(400).json({
            error: '缺少必要参数: text, refAudioUrl, refText'
        });
    }

    const queue = taskQueue.getInstance();
    const task = queue.createTask('clone', {
        text,
        language: language || 'Chinese',
        refAudio: refAudioUrl,
        refText,
        instruct: instruct || null
    });

    console.log(`[API] 声音克隆任务已创建：${task.id}`);

    res.json({
        success: true,
        taskId: task.id,
        message: '任务已提交，请在任务列表中查看进度'
    });
});

app.post('/api/design-voice', (req, res) => {
    const { text, language, instruct } = req.body;

    if (!text) {
        return res.status(400).json({ error: '缺少文本内容' });
    }

    if (!instruct) {
        return res.status(400).json({ error: '缺少声音描述 (instruct)' });
    }

    const queue = taskQueue.getInstance();
    const task = queue.createTask('design', {
        text,
        language: language || 'Chinese',
        instruct
    });

    console.log(`[API] 声音设计任务已创建：${task.id}`);

    res.json({
        success: true,
        taskId: task.id,
        message: '任务已提交，请在任务列表中查看进度'
    });
});

app.post('/api/upload', upload.single('audio'), (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: '没有上传文件' });
    }

    res.json({
        success: true,
        fileUrl: `/uploads/${req.file.filename}`,
        filename: req.file.filename
    });
});

app.post('/api/transcribe', upload.single('audio'), (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: '请上传音频文件' });
    }

    const { language } = req.body;

    const queue = taskQueue.getInstance();
    const task = queue.createTask('transcribe', {
        audioPath: `/uploads/${req.file.filename}`,
        language: language || 'zh'
    });

    console.log(`[API] 音频转文字任务已创建：${task.id}`);

    res.json({
        success: true,
        taskId: task.id,
        message: '转录任务已提交，请在任务列表中查看进度'
    });
});

app.get('/api/tasks/:id/text', (req, res) => {
    const queue = taskQueue.getInstance();
    const task = queue.getTask(req.params.id);

    if (!task) {
        return res.status(404).json({ success: false, error: '任务不存在' });
    }

    if (task.type !== 'transcribe') {
        return res.status(400).json({ success: false, error: '非转录任务' });
    }

    const txtPath = path.join(__dirname, 'output', `${task.id}.txt`);
    if (!fs.existsSync(txtPath)) {
        return res.status(404).json({ success: false, error: '转录结果文件不存在' });
    }

    const text = fs.readFileSync(txtPath, 'utf-8');
    res.json({ success: true, text });
});

app.get('/api/speakers', (req, res) => {
    const speakers = [
        { id: 'Vivian', name: 'Vivian', language: 'Chinese', description: '明亮活泼女声' },
        { id: 'Serena', name: 'Serena', language: 'Chinese', description: '温柔亲切女声' },
        { id: 'Uncle_Fu', name: 'Uncle_Fu', language: 'Chinese', description: '低沉沉稳男声' },
        { id: 'Dylan', name: 'Dylan', language: 'Chinese', description: '北京腔男声' },
        { id: 'Eric', name: 'Eric', language: 'Chinese', description: '四川话男声' },
        { id: 'Ryan', name: 'Ryan', language: 'English', description: '活力节奏感男声' },
        { id: 'Aiden', name: 'Aiden', language: 'English', description: '阳光美式男声' },
        { id: 'Ono_Anna', name: 'Ono_Anna', language: 'Japanese', description: '俏皮日语女声' },
        { id: 'Sohee', name: 'Sohee', language: 'Korean', description: '温暖韩语女声' }
    ];

    res.json({ speakers });
});

app.get('/api/languages', (req, res) => {
    const languages = [
        { code: 'Chinese', name: '中文' },
        { code: 'English', name: '英语' },
        { code: 'Japanese', name: '日语' },
        { code: 'Korean', name: '韩语' },
        { code: 'German', name: '德语' },
        { code: 'French', name: '法语' },
        { code: 'Russian', name: '俄语' },
        { code: 'Portuguese', name: '葡萄牙语' },
        { code: 'Spanish', name: '西班牙语' },
        { code: 'Italian', name: '意大利语' }
    ];

    res.json({ languages });
});

app.get('/api/tasks', (req, res) => {
    const queue = taskQueue.getInstance();
    queue.purgeOrphanedTasks();
    const tasks = queue.getAllTasks();
    res.json({ success: true, tasks });
});

app.get('/api/tasks/:id', (req, res) => {
    const queue = taskQueue.getInstance();
    const task = queue.getTask(req.params.id);
    
    if (!task) {
        return res.status(404).json({ success: false, error: '任务不存在' });
    }
    
    res.json({ success: true, task });
});

// Debug endpoint for testing TTS with full control
app.post('/api/debug', upload.single('refAudio'), async (req, res) => {
    const { 
        mode,           // 'generate' or 'clone'
        text, 
        language, 
        speaker,
        refText,
        useChunks,
        maxChars,
        device,
        verbose
    } = req.body;

    if (!text) {
        return res.status(400).json({ error: '缺少文本内容' });
    }

    if (mode === 'clone' && !req.file) {
        return res.status(400).json({ error: '克隆模式需要上传参考音频' });
    }

    const outputFile = `output/debug_${uuidv4()}.wav`;
    const outputPath = path.join(__dirname, outputFile);

    try {
        const args = [
            '--mode', mode || 'generate',
            '--model_path', mode === 'clone' ? MODEL_BASE_PATH : MODEL_VOICE_PATH,
            '--text', text,
            '--output', outputPath,
            '--language', language || 'Chinese'
        ];

        if (mode === 'generate') {
            args.push('--speaker', speaker || 'Vivian');
        } else if (mode === 'clone') {
            const refAudioPath = `/uploads/${req.file.filename}`;
            args.push('--ref_audio', refAudioPath);
            args.push('--ref_text', refText || '');
        }

        if (useChunks === 'true') {
            args.push('--use_chunks');
            if (maxChars) {
                args.push('--max_chars', maxChars);
            }
        }

        if (device) {
            args.push('--device', device);
        }

        if (verbose === 'true') {
            args.push('--verbose');
        }

        const result = await runPythonScript('debug_tts.py', args);
        
        // Parse debug info from result
        let debugInfo = {};
        try {
            const jsonMatch = result.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                debugInfo = JSON.parse(jsonMatch[0]);
            }
        } catch (e) {
            console.error('Failed to parse debug info:', e);
        }

        res.json({
            success: true,
            audioUrl: `/${outputFile}`,
            debugInfo: debugInfo,
            rawOutput: result,
            message: '调试完成'
        });
    } catch (error) {
        console.error('调试失败:', error);
        res.status(500).json({
            success: false,
            error: error.message || '调试失败',
            debugInfo: error.debugInfo || null
        });
    }
});

app.use((err, req, res, next) => {
    console.error('服务器错误:', err);
    res.status(500).json({
        success: false,
        error: err.message || '服务器内部错误'
    });
});

const certDir = path.join(__dirname, 'certs');
const certPath = path.join(certDir, 'cert.pem');
const keyPath = path.join(certDir, 'key.pem');

if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    const https = require('https');
    const sslOptions = {
        cert: fs.readFileSync(certPath),
        key: fs.readFileSync(keyPath)
    };
    https.createServer(sslOptions, app).listen(PORT, () => {
        console.log(`Qwen3-TTS WebUI 服务已启动: https://localhost:${PORT}`);
        console.log(`模型路径: ${MODEL_BASE_PATH}`);
        taskExecutor.getInstance();
    });
} else {
    app.listen(PORT, () => {
        console.log(`Qwen3-TTS WebUI 服务已启动: http://localhost:${PORT}`);
        console.log(`[WARN] 未找到 SSL 证书，使用 HTTP 模式。手机端录音功能将无法使用`);
        console.log(`模型路径: ${MODEL_BASE_PATH}`);
        taskExecutor.getInstance();
    });
}
