<template>
  <div class="container">
    <!-- 头部：标题与基础状态 -->
    <header>
      <div>
        <h1>
          <svg style="width: 28px; height: 28px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          YOLO26s-seg 智能分割训练平台
        </h1>
        <div class="subtitle">面向猪只多边形分割任务的轻量化一站式训练控制台</div>
      </div>
      
      <!-- 训练状态徽章 -->
      <div class="status-badge" :class="trainStatus.state">
        <span class="dot" :class="{ active: trainStatus.state === 'training' || trainStatus.state === 'preparing' }"></span>
        {{ stateLabels[trainStatus.state] || '未知状态' }}
      </div>
    </header>

    <div class="main-grid">
      <!-- 左侧：参数配置区域 -->
      <div class="glass-card">
        <div class="section-title">
          <svg style="width: 18px; height: 18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          训练参数配置
        </div>

        <form @submit.prevent="handleStartTrain">
          <!-- 基础训练配置 -->
          <div class="form-row-2">
            <div class="form-group">
              <label for="epochs">训练轮次 (Epochs)</label>
              <input type="number" id="epochs" v-model.number="form.epochs" min="1" max="1000" required :disabled="isTraining" />
            </div>
            <div class="form-group">
              <label for="batch">批次大小 (Batch Size)</label>
              <input type="number" id="batch" v-model.number="form.batch" min="1" max="128" required :disabled="isTraining" />
            </div>
          </div>

          <div class="form-row-2">
            <div class="form-group">
              <label for="lr0">初始学习率 (lr0)</label>
              <input type="number" id="lr0" v-model.number="form.lr0" step="0.0001" min="0.0001" max="0.1" required :disabled="isTraining" />
            </div>
            <div class="form-group">
              <label for="patience">早停耐心值 (Patience)</label>
              <input type="number" id="patience" v-model.number="form.patience" min="0" required :disabled="isTraining" />
            </div>
          </div>

          <div class="form-row-2">
            <div class="form-group">
              <label for="imgsz">图片尺寸 (Image Size)</label>
              <input type="number" id="imgsz" v-model.number="form.imgsz" step="32" min="64" max="2048" required :disabled="isTraining" />
              <div class="form-desc">建议为32的倍数，默认960</div>
            </div>
            <div class="form-group">
              <label for="device">训练设备 (Device)</label>
              <input type="text" id="device" v-model="form.device" placeholder="cpu 或 GPU 序号 0" required :disabled="isTraining" />
              <div class="form-desc">例如：cpu，0，1 或 0,1</div>
            </div>
          </div>

          <div class="form-group">
            <label for="split_ratio">数据集划分比例 (Train:Val:Test)</label>
            <input type="text" id="split_ratio" v-model="form.split_ratio" placeholder="8:1:1" required :disabled="isTraining" />
            <div class="form-desc">训练集、验证集、测试集比例，默认 8:1:1</div>
          </div>

          <!-- 数据增强配置 -->
          <div class="section-title" style="margin-top: 30px;">
            <svg style="width: 18px; height: 18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m11.314 11.314l.707.707M12 5a7 7 0 1 0 0 14 7 7 0 0 0 0-14z"/>
            </svg>
            数据增强配置
          </div>

          <div class="enhance-grid">
            <div class="form-group">
              <label>
                Mosaic 拼接比例 ({{ form.mosaic.toFixed(1) }})
                <span class="info-tooltip">?
                  <span class="tooltip-box">将4张图像拼接为1张。强迫模型识别多尺度目标并丰富背景，对小目标分割和泛化极有帮助。</span>
                </span>
              </label>
              <div class="slider-container">
                <input type="range" v-model.number="form.mosaic" min="0" max="1" step="0.1" :disabled="isTraining" />
                <span class="slider-value">{{ form.mosaic.toFixed(1) }}</span>
              </div>
            </div>

            <div class="form-group">
              <label>
                MixUp 混合比例 ({{ form.mixup.toFixed(1) }})
                <span class="info-tooltip">?
                  <span class="tooltip-box">将两张图像按随机权重融合成一张新图像。能大幅提升抗噪能力，但对单分类猪只分割推荐保持为0。</span>
                </span>
              </label>
              <div class="slider-container">
                <input type="range" v-model.number="form.mixup" min="0" max="1" step="0.1" :disabled="isTraining" />
                <span class="slider-value">{{ form.mixup.toFixed(1) }}</span>
              </div>
            </div>

            <div class="form-group">
              <label>
                CopyPaste 复制粘贴比例 ({{ form.copy_paste.toFixed(1) }})
                <span class="info-tooltip">?
                  <span class="tooltip-box">抠出图像中真实标注的猪只Polygon并随机粘贴到其他图像，能显著增加样本实例密度。</span>
                </span>
              </label>
              <div class="slider-container">
                <input type="range" v-model.number="form.copy_paste" min="0" max="1" step="0.1" :disabled="isTraining" />
                <span class="slider-value">{{ form.copy_paste.toFixed(1) }}</span>
              </div>
            </div>

            <div class="form-row-2">
              <div class="form-group">
                <label>
                  水平翻转 (fliplr)
                  <span class="info-tooltip">?
                    <span class="tooltip-box">以指定概率（如50%）将训练图片做左右镜像翻转，使模型适应对称角度的猪只。</span>
                  </span>
                </label>
                <div class="slider-container">
                  <input type="range" v-model.number="form.fliplr" min="0" max="1" step="0.1" :disabled="isTraining" />
                  <span class="slider-value">{{ form.fliplr.toFixed(1) }}</span>
                </div>
              </div>
              <div class="form-group">
                <label>
                  垂直翻转 (flipud)
                  <span class="info-tooltip">?
                    <span class="tooltip-box">以指定概率将训练图片做上下镜像翻转，若通道图集存在仰视俯视视角可适量开启。</span>
                  </span>
                </label>
                <div class="slider-container">
                  <input type="range" v-model.number="form.flipud" min="0" max="1" step="0.1" :disabled="isTraining" />
                  <span class="slider-value">{{ form.flipud.toFixed(1) }}</span>
                </div>
              </div>
            </div>

            <div class="form-group">
              <label>
                随机旋转角度 (degrees: 0 - 180°)
                <span class="info-tooltip">?
                  <span class="tooltip-box">对图片进行指定旋转角度范围内的随机旋转。增强模型对各种偏斜、旋转猪只形态的适应力。</span>
                </span>
              </label>
              <div class="slider-container">
                <input type="range" v-model.number="form.degrees" min="0" max="180" step="5" :disabled="isTraining" />
                <span class="slider-value">{{ form.degrees }}°</span>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div style="margin-top: 24px;">
            <button v-if="!isTraining" type="submit" class="btn btn-primary" :disabled="sysInfo.dataset_status !== 'ready'">
              <svg style="width: 18px; height: 18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              一键准备数据集并开始训练
            </button>
            <button v-else type="button" @click="handleStopTrain" class="btn btn-danger">
              <svg style="width: 18px; height: 18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="4" y="4" width="16" height="16" rx="2" ry="2"/>
              </svg>
              强行终止训练任务
            </button>
          </div>
        </form>

        <!-- 系统负载仪表盘 -->
        <div style="margin-top: 30px; border-top: 1px solid var(--border-color); padding-top: 20px;">
          <div class="section-title" style="font-size: 14px; margin-bottom: 12px; border-left: 2px solid var(--success);">
            服务器硬件负载 & 数据集状态
          </div>
          <div class="sys-info-row">
            <div class="sys-info-item">
              <div class="sys-info-label">CPU 使用率</div>
              <div class="sys-info-val">{{ sysInfo.cpu_percent }}%</div>
            </div>
            <div class="sys-info-item">
              <div class="sys-info-label">内存使用</div>
              <div class="sys-info-val">{{ sysInfo.memory_used_gb }} / {{ sysInfo.memory_total_gb }} GB</div>
            </div>
            <div class="sys-info-item">
              <div class="sys-info-label">GPU 加速</div>
              <div class="sys-info-val" :style="{ color: sysInfo.gpu_available ? 'var(--success)' : 'var(--text-muted)' }">
                {{ sysInfo.gpu_available ? '已启用' : '无' }}
              </div>
            </div>
            <div class="sys-info-item">
              <div class="sys-info-label">数据集压缩包</div>
              <div class="sys-info-val" :style="{ color: sysInfo.dataset_status === 'ready' ? 'var(--success)' : 'var(--error)' }">
                {{ sysInfo.dataset_status === 'ready' ? '就绪' : '缺失' }}
              </div>
            </div>
          </div>
          <div v-if="sysInfo.gpu_available && sysInfo.gpu_name !== 'N/A'" class="form-desc" style="text-align: center; margin-top: 10px;">
            检测到显卡: {{ sysInfo.gpu_name }}
          </div>
        </div>
      </div>

      <!-- 右侧：训练监控与控制台 -->
      <div class="monitor-area">
        <!-- 进度条面板 -->
        <div class="glass-card progress-panel">
          <div class="progress-header">
            <span style="font-weight: 600; font-size: 16px;">训练进度概览</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--primary);">
              Epoch: {{ trainStatus.progress.epoch }} / {{ trainStatus.progress.total_epochs }} ({{ trainStatus.progress.percent }}%)
            </span>
          </div>

          <!-- 进度条 -->
          <div class="progress-bar-track">
            <div class="progress-bar-fill" :style="{ width: trainStatus.progress.percent + '%' }"></div>
          </div>

          <!-- 指标卡网格 -->
          <div class="progress-stats-grid">
            <div class="stat-item">
              <span class="stat-label">预计剩余时间 (ETA)</span>
              <span class="stat-value" style="color: var(--warning);">{{ trainStatus.progress.eta }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Box Loss</span>
              <span class="stat-value">{{ trainStatus.progress.box_loss.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Segmentation Loss</span>
              <span class="stat-value">{{ trainStatus.progress.seg_loss.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Class Loss</span>
              <span class="stat-value">{{ trainStatus.progress.cls_loss.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">mAP50 (分割)</span>
              <span class="stat-value" style="color: var(--success);">{{ trainStatus.progress.map50.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">mAP50-95</span>
              <span class="stat-value" style="color: var(--success);">{{ trainStatus.progress.map50_95.toFixed(4) }}</span>
            </div>
          </div>
        </div>

        <!-- 终端日志控制台 -->
        <div class="console-panel">
          <div class="console-header">
            <div class="console-title">
              <span class="dot" :class="{ active: isTraining }"></span>
              YOLO 实时控制台日志
            </div>
            <div class="console-actions">
              <button class="console-btn" @click="clearLogs">清空控制台</button>
              <button class="console-btn" @click="scrollToBottom">滚动探底</button>
            </div>
          </div>
          
          <div class="console-output" ref="consoleRef">
            <div v-if="logs.length === 0" class="log-line system">
              [SYSTEM] 等待训练启动以显示实时日志流...
            </div>
            <div v-for="(log, idx) in logs" :key="idx" class="log-line" :class="{ system: log.startsWith('[SYSTEM]') }">
              {{ log }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue';

// 动态检测后端接口，开发环境指向 8000 端口，生产环境使用同源
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:9523'
  : window.location.origin;

// 状态文字映射表
const stateLabels = {
  idle: '等待训练',
  preparing: '正在解压并随机划分数据集',
  training: 'YOLO 训练进行中',
  completed: '训练成功结束',
  failed: '训练异常退出',
  stopped: '已手动终止训练'
};

// 默认表单参数
const form = reactive({
  epochs: 300,
  batch: 4,
  lr0: 0.001,
  patience: 50,
  imgsz: 960,
  device: '0',
  split_ratio: '8:1:1',
  mosaic: 0.5,
  mixup: 0.0,
  copy_paste: 0.3,
  fliplr: 0.5,
  flipud: 0.5,
  degrees: 180.0
});

// 系统负载及数据集状态
const sysInfo = reactive({
  cpu_percent: 0,
  memory_percent: 0,
  memory_used_gb: 0,
  memory_total_gb: 0,
  gpu_available: false,
  gpu_name: 'N/A',
  dataset_status: 'checking',
  dataset_size_mb: 0,
  dataset_path: ''
});

// 训练器进度和状态
const trainStatus = reactive({
  state: 'idle',
  progress: {
    epoch: 0,
    total_epochs: 300,
    percent: 0,
    eta: '--:--:--',
    box_loss: 0.0,
    seg_loss: 0.0,
    cls_loss: 0.0,
    dfl_loss: 0.0,
    mp: 0.0,
    mr: 0.0,
    map50: 0.0,
    map50_95: 0.0
  }
});

const logs = ref([]);
const consoleRef = ref(null);
let statusInterval = null;
let sysInfoInterval = null;
let eventSource = null;

// 快速判断是否正在处于活跃的训练状态
const isTraining = computed(() => {
  return trainStatus.state === 'training' || trainStatus.state === 'preparing';
});

// 定时获取系统信息
const fetchSysInfo = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/sysinfo`);
    if (res.ok) {
      const data = await res.json();
      Object.assign(sysInfo, data);
    }
  } catch (err) {
    console.error('获取系统状态失败:', err);
  }
};

// 定时获取训练状态和进度
const fetchTrainStatus = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (res.ok) {
      const data = await res.json();
      
      const prevState = trainStatus.state;
      Object.assign(trainStatus, data);
      
      // 如果状态从其他转变为 training/preparing，或者 eventSource 未创建，启动 SSE 接收日志
      if (isTraining.value && !eventSource) {
        startLogStream();
      }
      
      // 如果训练刚好结束，关闭 SSE 并进行最终数据更新
      if (!isTraining.value && eventSource) {
        closeLogStream();
      }
    }
  } catch (err) {
    console.error('获取训练状态失败:', err);
  }
};

// 启动实时日志 SSE 推送
const startLogStream = () => {
  if (eventSource) return;
  
  console.log('启动 SSE 实时日志接收...');
  eventSource = new EventSource(`${API_BASE}/api/logs`);
  
  eventSource.onmessage = (event) => {
    // 过滤掉 SSE 空心跳，添加至页面控制台
    if (event.data.trim()) {
      logs.value.push(event.data);
      // 保持控制台最新日志行数不超过 1000 行，防溢出崩溃
      if (logs.value.length > 1000) {
        logs.value.shift();
      }
      scrollToBottom();
    }
  };
  
  eventSource.onerror = (err) => {
    console.error('SSE 日志连接异常:', err);
    closeLogStream();
  };
};

// 关闭实时日志 SSE
const closeLogStream = () => {
  if (eventSource) {
    console.log('关闭 SSE 实时日志接收...');
    eventSource.close();
    eventSource = null;
  }
};

// 启动训练任务
const handleStartTrain = async () => {
  try {
    clearLogs();
    logs.value.push('[SYSTEM] 正在向后端请求启动 YOLOv8-seg 实例分割训练...');
    
    const res = await fetch(`${API_BASE}/api/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form)
    });
    
    if (res.ok) {
      const data = await res.json();
      logs.value.push('[SYSTEM] ' + data.message);
      // 启动 SSE 接收
      startLogStream();
      // 立即刷新一次状态
      fetchTrainStatus();
    } else {
      const errData = await res.json();
      logs.value.push(`[SYSTEM] 启动训练失败: ${errData.detail || '未知网络错误'}`);
    }
  } catch (err) {
    logs.value.push(`[SYSTEM] 网络连通错误: ${err.message}`);
  }
};

// 停止训练任务
const handleStopTrain = async () => {
  if (!confirm('警告：确定要强行中止当前正在运行的训练任务吗？')) {
    return;
  }
  
  try {
    logs.value.push('[SYSTEM] 正在发送中止信号...');
    const res = await fetch(`${API_BASE}/api/stop`, {
      method: 'POST'
    });
    
    if (res.ok) {
      const data = await res.json();
      logs.value.push('[SYSTEM] ' + data.message);
      closeLogStream();
      fetchTrainStatus();
    } else {
      const errData = await res.json();
      logs.value.push(`[SYSTEM] 停止训练请求失败: ${errData.detail}`);
    }
  } catch (err) {
    logs.value.push(`[SYSTEM] 无法连接到服务器进行终止: ${err.message}`);
  }
};

// 清空日志控制台
const clearLogs = () => {
  logs.value = [];
};

// 控制台自动滚到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (consoleRef.value) {
      consoleRef.value.scrollTop = consoleRef.value.scrollHeight;
    }
  });
};

onMounted(() => {
  // 首次拉取
  fetchSysInfo();
  fetchTrainStatus();
  
  // 定时器挂载
  statusInterval = setInterval(fetchTrainStatus, 1000);
  sysInfoInterval = setInterval(fetchSysInfo, 3000);
});

onUnmounted(() => {
  clearInterval(statusInterval);
  clearInterval(sysInfoInterval);
  closeLogStream();
});
</script>

<style scoped>
/* style.css 为全局设计，此处可为空或加额外补丁 */
</style>
