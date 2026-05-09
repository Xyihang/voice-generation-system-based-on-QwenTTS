const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

class TaskQueue {
    constructor() {
        this.tasks = new Map();
        this.taskDir = path.join(__dirname, '..', 'tasks');
        
        // 确保任务目录存在
        if (!fs.existsSync(this.taskDir)) {
            fs.mkdirSync(this.taskDir, { recursive: true });
        }
        
        // 恢复未完成的任务
        this.recoverTasks();
    }

    // 创建新任务
    createTask(type, params) {
        const taskId = uuidv4();
        const task = {
            id: taskId,
            type, // 'generate' or 'clone'
            status: 'pending', // pending, running, completed, failed
            progress: 0,
            params,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            result: null,
            error: null
        };

        this.tasks.set(taskId, task);
        this.saveTask(task);
        
        return task;
    }

    // 获取任务状态
    getTask(taskId) {
        return this.tasks.get(taskId);
    }

    // 获取所有任务
    getAllTasks() {
        return Array.from(this.tasks.values()).sort((a, b) => {
            return new Date(b.createdAt) - new Date(a.createdAt);
        });
    }

    // 更新任务状态
    updateTask(taskId, updates) {
        const task = this.tasks.get(taskId);
        if (!task) {
            throw new Error(`Task ${taskId} not found`);
        }

        Object.assign(task, updates);
        task.updatedAt = new Date().toISOString();
        
        this.tasks.set(taskId, task);
        this.saveTask(task);
        
        return task;
    }

    // 标记任务完成
    completeTask(taskId, result) {
        return this.updateTask(taskId, {
            status: 'completed',
            progress: 100,
            result,
            completedAt: new Date().toISOString()
        });
    }

    // 标记任务失败
    failTask(taskId, error) {
        return this.updateTask(taskId, {
            status: 'failed',
            error: error.message || String(error),
            failedAt: new Date().toISOString()
        });
    }

    // 保存任务到文件
    saveTask(task) {
        const taskFile = path.join(this.taskDir, `${task.id}.json`);
        fs.writeFileSync(taskFile, JSON.stringify(task, null, 2), 'utf-8');
    }

    // 恢复未完成的任务，清理无效任务（音频文件已删除的）
    recoverTasks() {
        if (!fs.existsSync(this.taskDir)) {
            return;
        }

        const outputDir = path.join(__dirname, '..', 'output');
        const files = fs.readdirSync(this.taskDir);
        let removed = 0;

        for (const file of files) {
            if (!file.endsWith('.json')) continue;

            try {
                const taskFile = path.join(this.taskDir, file);
                const taskData = JSON.parse(fs.readFileSync(taskFile, 'utf-8'));

                // 对已完成/已失败的任务，检查音频文件是否存在
                if (taskData.status === 'completed' || taskData.status === 'failed') {
                    const wavFile = path.join(outputDir, `${taskData.id}.wav`);
                    const txtFile = path.join(outputDir, `${taskData.id}.txt`);
                    if (!fs.existsSync(wavFile) && !fs.existsSync(txtFile)) {
                        fs.unlinkSync(taskFile);
                        removed++;
                        console.log(`[TaskQueue] 结果文件已删除，清理任务：${taskData.id} (${taskData.type})`);
                        continue;
                    }
                }

                this.tasks.set(taskData.id, taskData);
                console.log(`[TaskQueue] 恢复任务：${taskData.id} (${taskData.type}) - ${taskData.status}`);
            } catch (e) {
                console.error(`[TaskQueue] 恢复任务失败：${file}`, e);
            }
        }

        if (removed > 0) {
            console.log(`[TaskQueue] 已清理 ${removed} 个无效任务`);
        }
        console.log(`[TaskQueue] 已恢复 ${this.tasks.size} 个任务`);
    }

    // 清理音频文件已删除的任务
    purgeOrphanedTasks() {
        const outputDir = path.join(__dirname, '..', 'output');
        let removed = 0;

        for (const [taskId, task] of this.tasks) {
            if (task.status === 'completed' || task.status === 'failed') {
                const wavFile = path.join(outputDir, `${taskId}.wav`);
                const txtFile = path.join(outputDir, `${taskId}.txt`);
                if (!fs.existsSync(wavFile) && !fs.existsSync(txtFile)) {
                    this.tasks.delete(taskId);
                    const taskFile = path.join(this.taskDir, `${taskId}.json`);
                    if (fs.existsSync(taskFile)) {
                        fs.unlinkSync(taskFile);
                    }
                    removed++;
                }
            }
        }

        if (removed > 0) {
            console.log(`[TaskQueue] 清理了 ${removed} 个无效任务`);
        }
        return removed;
    }

    // 清理旧任务（保留最近 100 个）
    cleanup(maxTasks = 100) {
        const allTasks = this.getAllTasks();
        
        if (allTasks.length > maxTasks) {
            const toRemove = allTasks.slice(maxTasks);
            
            for (const task of toRemove) {
                this.tasks.delete(task.id);
                const taskFile = path.join(this.taskDir, `${task.id}.json`);
                if (fs.existsSync(taskFile)) {
                    fs.unlinkSync(taskFile);
                }
            }
            
            console.log(`[TaskQueue] 清理了 ${toRemove.length} 个旧任务`);
        }
    }
}

// 单例模式
let instance = null;

module.exports = {
    getInstance() {
        if (!instance) {
            instance = new TaskQueue();
        }
        return instance;
    }
};
