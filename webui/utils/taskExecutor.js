const { spawn } = require('child_process');
const path = require('path');
const taskQueue = require('./taskQueue');
const fs = require('fs');

const CONDA_PYTHON = 'C:/Users/xiyih/miniconda3/envs/qwen3-tts/python.exe';
const MODEL_BASE_PATH = 'd:/AI/QwenTTS/qwen3-tts-base-model/Qwen/Qwen3-TTS-12Hz-1.7B-Base';
const MODEL_VOICE_PATH = 'd:/AI/QwenTTS/qwen3-tts-model';
const MODEL_DESIGN_PATH = 'd:/AI/QwenTTS/qwen3-tts-model/Qwen3-TTS-12Hz-1.7B-VoiceDesign';

class TaskExecutor {
    constructor() {
        this.executingTasks = new Map();
        this.resetStuckTasks();
        this.startProcessing();
    }

    // 重置卡住的任务（服务器重启时，running状态的任务实际上已经不在执行了）
    resetStuckTasks() {
        const queue = taskQueue.getInstance();
        const allTasks = queue.getAllTasks();
        
        const stuckTasks = allTasks.filter(t => t.status === 'running');
        
        for (const task of stuckTasks) {
            console.log(`[TaskExecutor] 重置卡住的任务：${task.id}`);
            queue.updateTask(task.id, {
                status: 'pending',
                progress: 0
            });
        }
        
        if (stuckTasks.length > 0) {
            console.log(`[TaskExecutor] 已重置 ${stuckTasks.length} 个卡住的任务`);
        }
    }

    // 启动任务处理
    startProcessing() {
        console.log('[TaskExecutor] 开始监听任务队列...');
        
        // 每 5 秒检查一次任务队列
        setInterval(() => {
            this.processNextTask();
        }, 5000);

        // 每 60 秒清理一次无效任务
        setInterval(() => {
            const queue = taskQueue.getInstance();
            queue.purgeOrphanedTasks();
        }, 60000);
        
        // 立即检查一次
        setTimeout(() => this.processNextTask(), 1000);
    }

    // 处理下一个任务
    processNextTask() {
        const queue = taskQueue.getInstance();
        const allTasks = queue.getAllTasks();
        
        // 查找待处理的任务
        const pendingTask = allTasks.find(t => t.status === 'pending');
        
        if (!pendingTask) {
            return;
        }

        // 检查是否有正在执行的任务
        if (this.executingTasks.size > 0) {
            console.log('[TaskExecutor] 当前有任务正在执行，跳过');
            return;
        }

        // 开始执行任务
        this.executeTask(pendingTask);
    }

    // 执行单个任务
    async executeTask(task) {
        console.log(`[TaskExecutor] 开始执行任务：${task.id} (${task.type})`);
        
        // 更新任务状态为运行中
        const queue = taskQueue.getInstance();
        queue.updateTask(task.id, {
            status: 'running',
            progress: 10
        });

        this.executingTasks.set(task.id, task);

        try {
            let result;
            if (task.type === 'generate') {
                result = await this.executeGenerateTask(task);
            } else if (task.type === 'clone') {
                result = await this.executeCloneTask(task);
            } else if (task.type === 'design') {
                result = await this.executeDesignTask(task);
            } else {
                throw new Error(`未知任务类型：${task.type}`);
            }

            // 任务完成
            queue.completeTask(task.id, {
                message: '任务完成',
                audioUrl: `/output/${path.basename(result.output)}`
            });
            
            console.log(`[TaskExecutor] 任务完成：${task.id}`);
        } catch (error) {
            console.error(`[TaskExecutor] 任务失败：${task.id}`, error);
            queue.failTask(task.id, error);
        } finally {
            this.executingTasks.delete(task.id);
        }
    }

    // 写入配置文件用于跨进程传参（解决Windows中文编码问题）
    writeConfigFile(taskId, config) {
        const configPath = path.join(__dirname, '..', 'data', `${taskId}.json`);
        fs.mkdirSync(path.dirname(configPath), { recursive: true });
        fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
        return configPath;
    }

    // 执行生成任务
    executeGenerateTask(task) {
        return new Promise((resolve, reject) => {
            const outputFile = path.join(__dirname, '..', 'output', `${task.id}.wav`);
            
            const configPath = this.writeConfigFile(task.id, {
                model_path: MODEL_VOICE_PATH,
                text: task.params.text,
                output: outputFile,
                language: task.params.language || 'Chinese',
                speaker: task.params.speaker || 'Vivian',
                instruct: task.params.instruct || ''
            });

            const args = [
                path.join(__dirname, '..', 'scripts', 'generate_voice.py'),
                '--config', configPath
            ];

            console.log(`[TaskExecutor] 执行生成任务：${task.id}`);
            
            const pythonProcess = spawn(CONDA_PYTHON, ['-u', ...args], {
                cwd: path.join(__dirname, '..'),
                env: {
                    ...process.env,
                    PYTHONIOENCODING: 'utf-8',
                    PYTHONUTF8: '1',
                    PYTHONUNBUFFERED: '1'
                }
            });

            this._bindProcessHandlers(pythonProcess, task, outputFile, configPath, resolve, reject);
        });
    }

    // 执行克隆任务
    executeCloneTask(task) {
        return new Promise((resolve, reject) => {
            const outputFile = path.join(__dirname, '..', 'output', `${task.id}.wav`);
            
            const refAudioPath = task.params.refAudio.startsWith('/')
                ? path.join(__dirname, '..', task.params.refAudio)
                : task.params.refAudio;

            const configPath = this.writeConfigFile(task.id, {
                model_path: MODEL_BASE_PATH,
                text: task.params.text,
                ref_audio: refAudioPath,
                ref_text: task.params.refText,
                output: outputFile,
                language: task.params.language || 'Chinese',
                instruct: task.params.instruct || ''
            });

            const args = [
                path.join(__dirname, '..', 'scripts', 'clone_voice.py'),
                '--config', configPath
            ];

            console.log(`[TaskExecutor] 执行克隆任务：${task.id}`);
            
            const pythonProcess = spawn(CONDA_PYTHON, ['-u', ...args], {
                cwd: path.join(__dirname, '..'),
                env: {
                    ...process.env,
                    PYTHONIOENCODING: 'utf-8',
                    PYTHONUTF8: '1',
                    PYTHONUNBUFFERED: '1'
                }
            });

            this._bindProcessHandlers(pythonProcess, task, outputFile, configPath, resolve, reject);
        });
    }

    // 执行声音设计任务
    executeDesignTask(task) {
        return new Promise((resolve, reject) => {
            const outputFile = path.join(__dirname, '..', 'output', `${task.id}.wav`);
            
            const modelPath = fs.existsSync(MODEL_DESIGN_PATH) 
                ? MODEL_DESIGN_PATH 
                : 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign';
            
            const configPath = this.writeConfigFile(task.id, {
                model_path: modelPath,
                text: task.params.text,
                output: outputFile,
                language: task.params.language || 'Chinese',
                instruct: task.params.instruct || '',
                device: task.params.device || 'auto'
            });

            const args = [
                path.join(__dirname, '..', 'scripts', 'design_voice.py'),
                '--config', configPath
            ];

            console.log(`[TaskExecutor] 执行声音设计任务：${task.id}`);
            
            const pythonProcess = spawn(CONDA_PYTHON, ['-u', ...args], {
                cwd: path.join(__dirname, '..'),
                env: {
                    ...process.env,
                    PYTHONIOENCODING: 'utf-8',
                    PYTHONUTF8: '1',
                    PYTHONUNBUFFERED: '1'
                }
            });

            this._bindProcessHandlers(pythonProcess, task, outputFile, configPath, resolve, reject);
        });
    }

    _bindProcessHandlers(pythonProcess, task, outputFile, configPath, resolve, reject) {
        let stdout = '';
        let stderr = '';

        pythonProcess.stdout.on('data', (data) => {
            const output = data.toString();
            stdout += output;
            console.log(`[Task ${task.id}] ${output.trim()}`);

            const queue = taskQueue.getInstance();
            if (output.includes('[1/5]') || output.includes('[1/2]')) queue.updateTask(task.id, { progress: 20 });
            else if (output.includes('[2/5]')) queue.updateTask(task.id, { progress: 30 });
            else if (output.includes('[3/5]') || output.includes('[3/3]')) queue.updateTask(task.id, { progress: 40 });
            else if (output.includes('Generating chunk')) {
                const match = output.match(/chunk (\d+)\/(\d+)/);
                if (match) {
                    const progress = 40 + Math.round((parseInt(match[1]) / parseInt(match[2])) * 45);
                    queue.updateTask(task.id, { progress });
                }
            }
            else if (output.includes('[4/5]') || output.includes('[2/2]')) queue.updateTask(task.id, { progress: 90 });
            else if (output.includes('[5/5]') || output.includes('[DONE]') || output.includes('Output saved')) queue.updateTask(task.id, { progress: 100 });
        });

        pythonProcess.stderr.on('data', (data) => {
            const msg = data.toString();
            stderr += msg;
            const trimmed = msg.trim();
            if (trimmed.includes('Warning') || trimmed.includes('FutureWarning') || trimmed.includes('UserWarning') || trimmed.includes('pad_token_id')) {
                console.log(`[Task ${task.id}] [WARN] ${trimmed}`);
            } else {
                console.error(`[Task ${task.id}] [ERROR] ${trimmed}`);
            }
        });

        pythonProcess.on('close', (code) => {
            try { fs.unlinkSync(configPath); } catch(e) {}
            if (code === 0 || fs.existsSync(outputFile)) {
                resolve({
                    output: outputFile,
                    logs: stdout
                });
            } else {
                reject(new Error(`进程退出码：${code}\n${stderr}`));
            }
        });

        pythonProcess.on('error', (err) => {
            try { fs.unlinkSync(configPath); } catch(e) {}
            reject(err);
        });
    }
}

// 单例模式
let instance = null;

module.exports = {
    getInstance() {
        if (!instance) {
            instance = new TaskExecutor();
        }
        return instance;
    }
};
