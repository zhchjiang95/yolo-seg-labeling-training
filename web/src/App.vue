<template>
  <div class="container">
    <!-- 全局 Toast 轻提示容器 -->
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div v-for="toast in toasts" :key="toast.id" class="toast-item" :class="toast.type">
          <!-- 成功 Icon -->
          <svg v-if="toast.type === 'success'" style="width: 16px; height: 16px; color: var(--success); flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <!-- 警告 Icon -->
          <svg v-else-if="toast.type === 'warning'" style="width: 16px; height: 16px; color: var(--warning); flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <!-- 错误 Icon -->
          <svg v-else-if="toast.type === 'error'" style="width: 16px; height: 16px; color: var(--error); flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <!-- 消息/通知 Icon -->
          <svg v-else style="width: 16px; height: 16px; color: var(--primary); flex-shrink: 0;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
          <span>{{ toast.message }}</span>
        </div>
      </TransitionGroup>
    </div>

    <!-- 头部：标题与基础状态 -->
    <header>
      <div>
        <h1>
          <svg style="width: 20px; height: 20px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          YOLO26s-seg 智能分割训练平台
        </h1>
        <div class="subtitle">面向目标多边形分割任务的轻量化一站式训练控制台</div>
      </div>
      
      <!-- 头部右侧动作组：状态徽章、Tab 与 主题 -->
      <div style="display: flex; align-items: center; gap: 16px;">
        <div v-if="currentTab === 'train'" class="status-badge" :class="trainStatus.state">
          <span class="dot" :class="{ active: trainStatus.state === 'training' || trainStatus.state === 'preparing' }"></span>
          {{ stateLabels[trainStatus.state] || '未知状态' }}
        </div>
        
        <button class="theme-toggle-btn" @click="toggleTheme" title="切换主题">
          <!-- 亮色下显示月亮 -->
          <svg v-if="!isDark" style="width: 18px; height: 18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
          <!-- 暗色下显示太阳 -->
          <svg v-else style="width: 18px; height: 18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/>
            <line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/>
            <line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        </button>
      </div>
    </header>

    <!-- TAB 导航与数据集选择栏 -->
    <div class="tabs-container">
      <div class="nav-tabs">
        <div class="tab-item" :class="{ active: currentTab === 'train' }" @click="currentTab = 'train'">
          <svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
          </svg>
          模型训练
        </div>
        <div class="tab-item" :class="{ active: currentTab === 'label' }" @click="currentTab = 'label'">
          <svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
          </svg>
          数据标注
        </div>
      </div>

      <!-- 右侧数据集选择 -->
      <div class="dataset-select-bar">
        <label style="margin-bottom: 0; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;">
          <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          数据集：
        </label>
        <select v-model="currentDataset" class="dataset-select">
          <option v-for="ds in datasets" :key="ds" :value="ds">{{ ds }}</option>
        </select>

        <!-- 创建按钮 (仅在数据标注页签显示) -->
        <button v-if="currentTab === 'label'" class="create-ds-btn" @click="handleCreateDataset" title="创建新数据集">
          <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          新建数据集
        </button>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- TAB 1: 训练大屏                               -->
    <!-- ========================================== -->
    <div v-if="currentTab === 'train'" class="main-grid">
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
                  <span class="tooltip-box">将两张图像按随机权重融合成一张新图像。能大幅提升抗噪能力，但对单分类目标分割推荐保持为0。</span>
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
                  <span class="tooltip-box">抠出图像中真实标注的目标Polygon并随机粘贴到其他图像，能显著增加样本实例密度。</span>
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
                    <span class="tooltip-box">以指定概率（如50%）将训练图片做左右镜像翻转，使模型适应对称角度的目标。</span>
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
                  <span class="tooltip-box">对图片进行指定旋转角度范围内的随机旋转。增强模型对各种偏斜、旋转目标形态的适应力。</span>
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
            <div v-if="!isTraining" class="form-desc" style="text-align: center; margin-top: 8px; color: var(--text-muted); font-size: 11px;">
              提示：训练开始将清除上一次训练的结果
            </div>
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
              <div class="sys-info-label">数据集状态</div>
              <div class="sys-info-val" :style="{ color: sysInfo.dataset_status === 'ready' ? 'var(--success)' : 'var(--error)' }">
                {{ sysInfo.dataset_status === 'ready' ? '就绪' : '缺失' }}
              </div>
            </div>
          </div>
          <div class="form-desc" style="text-align: center; margin-top: 10px;">
            数据源: {{ sysInfo.dataset_path }}
          </div>
          <div v-if="sysInfo.gpu_available && sysInfo.gpu_name !== 'N/A'" class="form-desc" style="text-align: center; margin-top: 5px;">
            检测到显卡: {{ sysInfo.gpu_name }}
          </div>
        </div>
      </div>

      <!-- 右侧：训练监控与控制台 -->
      <div class="monitor-area">
        <!-- 进度条面板 -->
        <div class="glass-card progress-panel">
          <!-- 1. 正在训练时的头部 -->
          <div v-if="isTraining" class="progress-header">
            <span style="font-weight: 600; font-size: 16px; display: flex; align-items: center; gap: 8px;">
              训练进度概览
              <span v-if="trainStatus.dataset" class="history-badge">
                数据集: {{ trainStatus.dataset }}
              </span>
            </span>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--primary);">
              Epoch: {{ trainStatus.progress.epoch }} / {{ trainStatus.progress.total_epochs }} ({{ trainStatus.progress.percent }}%)
            </span>
          </div>
          <!-- 2. 没在训练，且有最近训练历史时的头部 -->
          <div v-else-if="trainStatus.last_run && trainStatus.last_run.has_data" class="progress-header history">
            <span style="font-weight: 600; font-size: 16px; display: flex; align-items: center; gap: 8px;">
              <svg style="width: 18px; height: 18px; color: var(--success);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              最近一次训练结果概览
            </span>
            <span class="history-badge">
              数据集: {{ trainStatus.last_run.dataset }}
            </span>
          </div>
          <!-- 3. 没在训练，且无训练历史时的头部 -->
          <div v-else class="progress-header">
            <span style="font-weight: 600; font-size: 16px;">训练进度概览</span>
            <span style="font-size: 13px; color: var(--text-muted);">暂无训练结果，请启动训练</span>
          </div>

          <!-- 进度条 -->
          <div v-if="isTraining" class="progress-bar-track">
            <div class="progress-bar-fill" :style="{ width: trainStatus.progress.percent + '%' }"></div>
          </div>
          <div v-else-if="trainStatus.last_run && trainStatus.last_run.has_data" class="progress-bar-track history">
            <div class="progress-bar-fill completed" :style="{ width: '100%' }"></div>
          </div>

          <!-- 指标卡网格 -->
          <!-- 训练时的指标卡 -->
          <div v-if="isTraining" class="progress-stats-grid">
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
          
          <!-- 没在训练，且有最近训练历史时的指标卡 -->
          <div v-else-if="trainStatus.last_run && trainStatus.last_run.has_data" class="progress-stats-grid history">
            <div class="stat-item">
              <span class="stat-label">完成轮次 (Epochs)</span>
              <span class="stat-value" style="color: var(--primary);">
                {{ trainStatus.last_run.metrics.epoch }} / {{ trainStatus.last_run.meta.epochs || 300 }}
              </span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Box Loss</span>
              <span class="stat-value">{{ trainStatus.last_run.metrics.box_loss.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Segmentation Loss</span>
              <span class="stat-value">{{ trainStatus.last_run.metrics.seg_loss.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Class Loss</span>
              <span class="stat-value">{{ trainStatus.last_run.metrics.cls_loss.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">mAP50 (分割)</span>
              <span class="stat-value" style="color: var(--success);">{{ trainStatus.last_run.metrics.map50.toFixed(4) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">mAP50-95</span>
              <span class="stat-value" style="color: var(--success);">{{ trainStatus.last_run.metrics.map50_95.toFixed(4) }}</span>
            </div>
          </div>

          <!-- 没在训练且无历史记录 -->
          <div v-else class="progress-stats-grid empty" style="display: block;">
            <div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">
              等待启动训练。启动后将在此处实时显示训练各项指标与进度。
            </div>
          </div>

          <!-- 历史训练时的附加操作区：下载权重与效果图 -->
          <div v-if="!isTraining && trainStatus.last_run && trainStatus.last_run.has_data" class="history-actions-area">
            <div class="action-buttons" style="display: flex; gap: 12px; width: 100%;">
              <button 
                type="button"
                class="btn btn-success" 
                :disabled="!trainStatus.last_run.has_best_weight"
                @click="downloadBestWeight"
                style="display: flex; align-items: center; justify-content: center; gap: 8px; flex: 1; padding: 10px; font-weight: 600;"
              >
                <svg style="width: 18px; height: 18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                </svg>
                下载最佳权重模型 (best.pt)
              </button>
            </div>

            <!-- 展示训练曲线 results.png -->
            <div v-if="trainStatus.last_run.results_png" class="results-chart-container">
              <div class="chart-title">训练评估曲线 (results.png)</div>
              <div class="chart-wrapper">
                <img :src="getResultsPngUrl(trainStatus.last_run.results_png)" alt="Training Results Chart" class="results-chart-img" />
              </div>
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

    <!-- ========================================== -->
    <!-- TAB 2: 数据标注平台                           -->
    <!-- ========================================== -->
    <div v-else class="annotator-grid">
      <!-- 1. 左栏：图片管理 -->
      <div class="glass-card file-list-card">
        <div class="section-title" style="margin-bottom: 12px; font-size: 16px;">
          图集列表 (共 {{ imageList.length }} 张)
        </div>
        
        <!-- 搜索 -->
        <div class="file-search-box">
          <input type="text" v-model="searchQuery" placeholder="搜索图片文件名..." style="padding: 8px 12px; font-size: 13px;" />
        </div>

        <!-- 快速过滤 Tab 栏 -->
        <div class="filter-tab-bar">
          <button class="filter-tab-btn" :class="{ active: filterStatus === 'labeled' }" @click="filterStatus = 'labeled'">
            已标 ({{ imageList.filter(img => img.status === 'labeled').length }})
          </button>
          <button class="filter-tab-btn" :class="{ active: filterStatus === 'unlabeled' }" @click="filterStatus = 'unlabeled'">
            未标 ({{ imageList.filter(img => img.status === 'unlabeled').length }})
          </button>
          <button class="filter-tab-btn" :class="{ active: filterStatus === 'negative' }" @click="filterStatus = 'negative'">
            负样本 ({{ imageList.filter(img => img.status === 'negative').length }})
          </button>
        </div>

        <!-- 点击/拖拽上传 -->
        <div class="upload-area" @click="triggerUpload" @dragover.prevent @drop.prevent="handleFileDrop">
          <svg style="width: 20px; height: 20px; margin: 0 auto 6px; display: block;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
          </svg>
          点击或拖入图片到此处
          <input type="file" ref="uploadInputRef" style="display: none;" multiple accept="image/*" @change="handleFileUpload" />
        </div>

        <!-- 图片列表 -->
        <div class="file-list-container">
          <div v-if="filteredImageList.length === 0" style="text-align: center; color: var(--text-muted); font-size: 13px; margin-top: 20px;">
            暂无图片
          </div>
          <div v-for="(img, idx) in filteredImageList" :key="img.name" class="file-item" :class="{ active: currentImage && currentImage.name === img.name }" @click="selectImage(img)">
            <div style="display: flex; align-items: center; gap: 6px; overflow: hidden; flex: 1;">
              <!-- 序号展示 -->
              <span class="file-item-idx" style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); flex-shrink: 0; min-width: 20px;">{{ idx + 1 }}</span>
              <span class="file-item-name" :title="img.name" style="max-width: 135px;">{{ img.name }}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
              <!-- 显式区分文字 Badge -->
              <span class="status-badge-inline" :class="img.status">
                {{ img.status === 'labeled' ? '已标 ' + (img.label_count || 0) + ' 个' : (img.status === 'negative' ? '负样本' : '未标') }}
              </span>
              <button class="file-item-delete-btn" @click="deleteImage(img.name, $event)" title="删除图片">
                <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. 中栏：标注主画布 -->
      <div class="glass-card canvas-card">
        <!-- 标注控制工具栏 -->
        <div class="canvas-toolbar">
          <!-- 工具模式选择 -->
          <div style="display: flex; gap: 6px; align-items: center;">
            <button class="tool-btn" :class="{ active: activeTool === 'edit' }" @click="setTool('edit')" title="选择/调整多边形及顶点">
              <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 15 13 9 17 5 3"/>
              </svg>
              编辑模式
            </button>
            <button class="tool-btn" :class="{ active: activeTool === 'draw' }" @click="setTool('draw')" title="点击图片手动打点，双击闭合多边形">
              <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
              手动标注
            </button>
            <!-- SAM 辅助智能标注 (包含向下悬浮保持与控制面板) -->
            <div class="sam-popover-wrapper" style="position: relative; display: inline-block;">
              <button 
                class="tool-btn" 
                :class="{ active: activeTool === 'sam' }" 
                @click="setTool('sam')" 
                title="SAM辅助：左键正点(目标)，右键负点(排除)，Enter确认"
              >
                <span v-if="isSamPredicting" class="spinner" style="margin-right: 4px;"></span>
                <svg v-else style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                </svg>
                SAM辅助
              </button>

              <!-- 处于 SAM 模式时在按钮下方悬浮显示的保持控制面板 -->
              <transition name="popover-fade">
                <div v-if="activeTool === 'sam'" class="sam-popover-panel" @click.stop>
                  <div class="popover-arrow"></div>
                  
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; font-size: 11px;">
                    <span style="font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 4px;">
                      🔮 SAM 辅助面板
                    </span>
                    <span v-if="samPrompts.length > 0" class="status-badge-inline labeled">
                      {{ samPrompts.filter(p => p.label === 1).length }}正 / {{ samPrompts.filter(p => p.label === 0).length }}负
                    </span>
                  </div>

                  <!-- 核心操作按钮组 -->
                  <div style="display: flex; flex-direction: column; gap: 6px;">
                    <button
                      class="sam-confirm-btn"
                      :disabled="!samPreviewPolygon || isSamPredicting"
                      @click="confirmSAM"
                      title="确认当前 SAM 多边形并保存到实例列表中 (快捷键 Enter)"
                    >
                      <span v-if="isSamPredicting" class="spinner" style="margin-right: 6px;"></span>
                      <svg v-else style="width: 14px; height: 14px; margin-right: 4px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                      {{ isSamPredicting ? '推理中...' : '保持标注 (Enter)' }}
                    </button>

                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 10.5px; color: var(--text-muted); padding-top: 2px;">
                      <span>Esc 撤销打点</span>
                      <button 
                        v-if="samPrompts.length > 0"
                        @click="clearSAMPrompts"
                        style="background: transparent; border: none; color: var(--text-muted); cursor: pointer; text-decoration: underline; font-size: 10.5px;"
                      >
                        清空打点
                      </button>
                    </div>
                  </div>
                </div>
              </transition>
            </div>


            <!-- 模型识别控件块 (点击展开悬浮 Popover 选择模型并执行识别或识别+优化) -->
            <div class="model-popover-wrapper" style="position: relative; display: inline-block;">
              <button 
                class="tool-btn" 
                :class="{ active: showModelPopover }"
                :disabled="!currentImage || isAutoDetecting || isAutoDetectAndRefining" 
                style="border-color: #a855f7; color: #a855f7; background: rgba(168, 85, 247, 0.08); font-weight: 600;" 
                title="点击展开选择模型权重，支持普通识别或识别后自动使用 SAM 优化"
                @click.stop="toggleModelPopover"
              >
                <span v-if="isAutoDetecting || isAutoDetectAndRefining" class="spinner" style="margin-right: 4px;"></span>
                <span v-else style="font-size: 13px; margin-right: 2px;">✨</span>
                <span>模型识别</span>
                <svg style="width: 8px; height: 8px; margin-left: 2px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </button>
              
              <!-- 悬浮在按钮下方的 Popover 弹窗 -->
              <transition name="popover-fade">
                <div v-if="showModelPopover" class="model-popover-panel" @click.stop>
                  <div class="popover-arrow"></div>
                  
                  <div class="model-popover-header">
                    <span style="font-weight: 600; font-size: 12px; color: var(--text-primary); display: flex; align-items: center; gap: 4px;">
                      ✨ YOLO 模型目标识别
                    </span>
                    <button class="popover-close-btn" @click="showModelPopover = false" title="关闭">×</button>
                  </div>

                  <div class="model-popover-body">
                    <div style="margin-bottom: 12px;">
                      <label style="font-size: 11px; color: var(--text-secondary); margin-bottom: 5px; display: block;">选择分割权重：</label>
                      <select v-model="selectedModelPath" class="model-popover-select">
                        <option v-for="model in modelsList" :key="model.path" :value="model.path">
                          {{ model.name }} ({{ model.type === 'trained' ? '训练产物' : '内置权重' }})
                        </option>
                      </select>
                      <div v-if="modelsList.length === 0" style="font-size: 10.5px; color: var(--warning); margin-top: 4px;">
                        未检测到可用权重，请检查 models/ 或 runs/ 目录
                      </div>
                    </div>

                    <!-- 动作按钮组：识别 & 识别并使用SAM优化 -->
                    <div style="display: flex; gap: 8px;">
                      <button 
                        class="model-popover-detect-btn" 
                        :disabled="!currentImage || isAutoDetecting || isAutoDetectAndRefining || !selectedModelPath" 
                        @click="handleDetectOnly"
                        title="使用选中的 YOLO 模型进行目标实例分割"
                      >
                        <span v-if="isAutoDetecting" class="spinner" style="margin-right: 4px;"></span>
                        <span>{{ isAutoDetecting ? '识别中...' : '全图识别' }}</span>
                      </button>

                      <button 
                        class="model-popover-refine-btn" 
                        :disabled="!currentImage || isAutoDetecting || isAutoDetectAndRefining || !selectedModelPath" 
                        @click="handleDetectAndRefine"
                        title="使用选中的 YOLO 模型检测出目标后，立即通过 SAM 自动重分割优化全图边缘"
                      >
                        <span v-if="isAutoDetectAndRefining" class="spinner" style="margin-right: 4px;"></span>
                        <span v-else style="font-size: 11px; margin-right: 2px;">✨</span>
                        <span>{{ isAutoDetectAndRefining ? '识别并优化中...' : '识别并SAM优化' }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </transition>
            </div>


            <!-- Prompt 开放词汇智能识别控件块 (按需点击展开悬浮 Popover) -->
            <div class="prompt-popover-wrapper" style="position: relative; display: inline-block;">
              <button 
                class="tool-btn" 
                :class="{ active: showPromptPopover }"
                :disabled="!currentImage" 
                style="border-color: rgba(99, 102, 241, 0.4); color: var(--primary); background: rgba(99, 102, 241, 0.08); font-weight: 600;" 
                @click.stop="togglePromptPopover"
                title="点击展开 Prompt 开放词汇智能识别"
              >
                <svg style="width: 14px; height: 14px; color: var(--primary); margin-right: 2px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <span>✨ Prompt 识别</span>
              </button>

              <!-- 悬浮在按钮上方的 Popover 弹窗 -->
              <transition name="popover-fade">
                <div v-if="showPromptPopover" class="prompt-popover-panel" @click.stop>
                  <div class="prompt-popover-header">
                    <span style="font-weight: 600; font-size: 12px; color: var(--text-primary); display: flex; align-items: center; gap: 4px;">
                      ✨ Prompt 开放词汇识别
                    </span>
                    <button class="popover-close-btn" @click="showPromptPopover = false" title="关闭">×</button>
                  </div>

                  <div class="prompt-popover-body">
                    <div style="margin-bottom: 8px;">
                      <label style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; display: block;">提示词 (支持逗号分隔多个词汇)：</label>
                      <input 
                        type="text" 
                        v-model="promptText" 
                        placeholder="如 pig, person..." 
                        class="prompt-popover-input"
                        @keyup.enter="promptDetect"
                      />
                    </div>

                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px;">
                      <label style="font-size: 11px; color: var(--text-secondary); white-space: nowrap;">置信度阈值 (Conf):</label>
                      <input 
                        type="number" 
                        v-model.number="promptConf" 
                        step="0.05" 
                        min="0.01" 
                        max="0.9" 
                        class="prompt-popover-conf-input"
                        title="置信度阈值。如未识别到可尝试调低（如 0.01）"
                      />
                    </div>

                    <button 
                      class="prompt-popover-submit-btn" 
                      :disabled="!currentImage || isPromptDetecting || !promptText.trim()" 
                      @click="promptDetect"
                    >
                      <span v-if="isPromptDetecting" class="spinner" style="margin-right: 6px;"></span>
                      {{ isPromptDetecting ? '正在识别全图目标...' : '开始识别' }}
                    </button>
                  </div>
                  <div class="popover-arrow"></div>
                </div>
              </transition>
            </div>

            <button class="tool-btn" :class="{ active: activeTool === 'pan' }" @click="setTool('pan')" title="手形：左键拖拽平移图片">


              <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 10V8a7 7 0 0 1 14 0v2M12 3v5"/>
              </svg>
              拖拽
            </button>
            <button class="tool-btn" :class="{ active: activeTool === 'eraser' }" @click="setTool('eraser')" title="橡皮擦：左键涂抹擦除顶点，[ ] 键调节半径">
              <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 20H7L3 16C2 15 2 13 3 12L13 2L22 11L20 13L20 20Z"/>
                <line x1="18" y1="9" x2="12" y2="15"/>
              </svg>
              橡皮擦
            </button>
          </div>

          <!-- 清理与保存动作组 -->
          <div style="display: flex; gap: 8px;">
            <button class="tool-btn" @click="saveAsNegative" :disabled="!currentImage" style="background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff; border-color: transparent;" title="保存此图片为负样本，标注将清空且重命名图片">
              保存为负样本
            </button>
            <button class="tool-btn" @click="clearPolygons" :disabled="polygons.length === 0" title="清空当前图片所有多边形">
              清空
            </button>
            <button class="tool-btn active" @click="saveAnnotations" :disabled="!currentImage" style="background: var(--primary-gradient);">
              保存标注
            </button>
          </div>
        </div>

        <!-- 标注辅助属性配置栏 (独立的工具栏第二行) -->
        <div class="canvas-subtoolbar">
          <!-- 属性 1: 标注填充透明度 -->
          <div class="subtoolbar-item">
            <svg style="width: 13px; height: 13px; color: var(--primary);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
            </svg>
            <span class="subtoolbar-label">标注区域填充透明度:</span>
            <input type="range" v-model.number="polyFillOpacity" min="0.1" max="0.8" step="0.05" class="subtoolbar-slider" title="调节多边形颜色填充透明度" />
            <span class="subtoolbar-value">{{ Math.round(polyFillOpacity * 100) }}%</span>
          </div>

          <!-- 属性 2: 擦除半径 (仅橡皮擦或 Alt 涂抹模式时显示) -->
          <div v-if="activeTool === 'eraser' || (activeTool === 'edit' && altPressed)" class="subtoolbar-item" style="border-left: 1px solid var(--border-color); padding-left: 12px; margin-left: 4px;">
            <svg style="width: 13px; height: 13px; color: var(--warning);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="9"/>
            </svg>
            <span class="subtoolbar-label">橡皮擦半径:</span>
            <input type="range" v-model.number="eraserRadius" min="5" max="100" step="1" class="subtoolbar-slider" title="调节擦除顶点半径" />
            <span class="subtoolbar-value">{{ eraserRadius }}px</span>
          </div>

          <!-- 属性 3: 当前选中的标注分类指示 -->
          <div class="subtoolbar-item" style="margin-left: auto;">
            <span class="subtoolbar-label">当前标注类别:</span>
            <span class="current-class-tag" :style="{ background: getPolyColor(activeClassIndex) + '20', color: getPolyColor(activeClassIndex), borderColor: getPolyColor(activeClassIndex) }">
              <span class="tag-dot" :style="{ background: getPolyColor(activeClassIndex) }"></span>
              {{ classes[activeClassIndex] || '默认类别' }}
            </span>
          </div>
        </div>

        <!-- 标注操作提示语 -->
        <div v-if="currentImage" style="background: rgba(99,102,241,0.06); padding: 8px 12px; border-radius: 6px; font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; border-left: 3px solid var(--primary);">
          <span v-if="activeTool === 'edit'">💡 <strong>编辑模式</strong>: 点击多边形选中，拖动顶点微调；拖动边线上的<strong>半透明中点</strong>可直接插入新顶点；双击顶点删除点；<strong>按住 Alt 键拖动鼠标可直接涂抹擦除顶点</strong>；Delete 键删除选中多边形。</span>
          <span v-else-if="activeTool === 'draw'">✏️ <strong>手动打点</strong>: 鼠标左键在目标边缘点击，绘制多边形轮廓。可按 <strong>Ctrl+Z</strong> 撤销上一个点。双击，或再次点击<strong>第一个点</strong>可闭合多边形完成创建。Esc 取消。</span>
          <span v-else-if="activeTool === 'sam'">🔮 <strong>SAM智能辅助</strong>: 鼠标<strong>左键</strong>点击目标区域生成绿点(指明前景)，<strong>右键</strong>点击背景生成红点(排除背景)。实时生成紫色预览虚线，满意后按 <strong>Enter 键</strong> 确认转化为多边形，Esc 撤销。</span>
          <span v-else-if="activeTool === 'eraser'">🧽 <strong>橡皮擦模式</strong>: 按住鼠标左键并在要擦除的顶点区域内拖动涂抹，即可快速成批清除顶点。使用 <strong>[</strong> 和 <strong>]</strong> 键或滑块可调节擦除半径。</span>
          <span v-else-if="activeTool === 'pan'">🤚 <strong>手形拖拽</strong>: 按住鼠标左键并移动可以自由平移画布。在任何模式下，<strong>滚动鼠标滚轮</strong>均可缩放画布，<strong>按住空格键</strong>或使用<strong>鼠标右键拖动</strong>也可以随时平移。</span>
        </div>

        <!-- 画布核心工作区 -->
        <div class="canvas-workspace" :class="{ 'draw-mode': activeTool === 'draw', 'panning': activeTool === 'pan' || spacePressed || rightMouseDown }" @wheel.prevent="handleZoom" @mousedown="startPan" @contextmenu.prevent>
          <div v-if="!currentImage" style="color: var(--text-muted); text-align: center; font-size: 14px; margin-top: 10%;">
            请在左侧列表中选择一张图片开始标注
          </div>
          
          <!-- 图片与 SVG 渲染包裹器，绑定平移和缩放 -->
          <div v-else class="canvas-container" :style="{ transform: `translate(${panX}px, ${panY}px) scale(${zoom})` }">
            <img :src="currentImageSrc" class="canvas-img" @load="onImageLoad" />
            
            <!-- SVG 多边形编辑渲染图层，像素级 viewBox 同步 -->
            <svg :viewBox="`0 0 ${imgNaturalWidth} ${imgNaturalHeight}`" class="svg-overlay" @mousedown="handleSVGMouseDown" @click="handleSVGClick">
              <!-- 1. 渲染所有已确定的多边形 -->
              <polygon
                v-for="(poly, polyIndex) in polygons"
                v-show="!poly.hidden"
                :key="'poly-' + polyIndex"
                :points="poly.points.map(pt => `${pt[0] * imgNaturalWidth},${pt[1] * imgNaturalHeight}`).join(' ')"
                class="svg-polygon"
                :class="{ active: activePolyIndex === polyIndex }"
                :style="{
                  fill: getPolyColor(poly.class_id),
                  fillOpacity: activePolyIndex === polyIndex ? Math.min(polyFillOpacity + 0.2, 0.9) : polyFillOpacity,
                  stroke: getPolyColor(poly.class_id)
                }"
                @mousedown="handlePolygonMouseDown($event, polyIndex)"
              />

              <!-- 2. 编辑模式下：渲染当前选中的多边形顶点与加宽边线 hitbox -->
              <g v-if="activeTool === 'edit' && activePolyIndex !== null && polygons[activePolyIndex] && !polygons[activePolyIndex].hidden">
                <!-- 加宽隐形边线 hitbox，点击即可在点击处添加新顶点并滑行拖拽微调 -->
                <line
                  v-for="line in getPolygonLines(polygons[activePolyIndex])"
                  :key="'edge-' + line.index"
                  :x1="line.x1"
                  :y1="line.y1"
                  :x2="line.x2"
                  :y2="line.y2"
                  class="svg-edge-hitbox"
                  @mousedown.stop="insertPointOnEdge($event, activePolyIndex, line.index)"
                  title="在此边上按下鼠标并拖动可直接插入并微调顶点"
                />

                <!-- 真实的多边形顶点 -->
                <circle
                  v-for="(pt, ptIndex) in polygons[activePolyIndex].points"
                  :key="'pt-' + ptIndex"
                  :cx="pt[0] * imgNaturalWidth"
                  :cy="pt[1] * imgNaturalHeight"
                  r="1.8"
                  class="svg-point"
                  :class="{ 'active-drag': dragInfo && dragInfo.polyIndex === activePolyIndex && dragInfo.ptIndex === ptIndex }"
                  @mousedown.stop="startDragPoint($event, activePolyIndex, ptIndex)"
                  @dblclick.stop="deletePoint(activePolyIndex, ptIndex)"
                  title="双击删除此点"
                />
              </g>

              <!-- 3. 手动绘制模式下：绘制临时点、连线和未闭合的多边形 -->
              <g v-if="activeTool === 'draw' && activePolygonPoints.length > 0">
                <!-- 临时绘制预览多边形（3点及以上提供实时颜色填充预览） -->
                <polygon
                  v-if="activePolygonPoints.length >= 3"
                  :points="activePolygonPoints.map(pt => `${pt[0] * imgNaturalWidth},${pt[1] * imgNaturalHeight}`).join(' ')"
                  class="svg-poly-temp"
                  :style="{ fill: getPolyColor(activeClassIndex), fillOpacity: polyFillOpacity * 0.75, stroke: getPolyColor(activeClassIndex) }"
                />
                <!-- 临时绘制预览多边形边线 -->
                <polyline
                  :points="activePolygonPoints.map(pt => `${pt[0] * imgNaturalWidth},${pt[1] * imgNaturalHeight}`).join(' ')"
                  class="svg-line-temp"
                  :style="{ stroke: getPolyColor(activeClassIndex) }"
                />
                <!-- 鼠标当前位置到最后一个点的虚线 -->
                <line
                  v-if="mousePos"
                  :x1="activePolygonPoints[activePolygonPoints.length - 1][0] * imgNaturalWidth"
                  :y1="activePolygonPoints[activePolygonPoints.length - 1][1] * imgNaturalHeight"
                  :x2="mousePos[0]"
                  :y2="mousePos[1]"
                  class="svg-line-temp"
                  :style="{ stroke: getPolyColor(activeClassIndex) }"
                />
                <!-- 首尾虚线连线预览闭合效果 -->
                <line
                  v-if="activePolygonPoints.length >= 2"
                  :x1="activePolygonPoints[0][0] * imgNaturalWidth"
                  :y1="activePolygonPoints[0][1] * imgNaturalHeight"
                  :x2="activePolygonPoints[activePolygonPoints.length - 1][0] * imgNaturalWidth"
                  :y2="activePolygonPoints[activePolygonPoints.length - 1][1] * imgNaturalHeight"
                  style="stroke: var(--primary); stroke-width: 1px; stroke-dasharray: 2 4; opacity: 0.6;"
                />
                <!-- 首点专属的高亮动态脉冲扩散圈（方便识别闭合点） -->
                <circle
                  v-if="activePolygonPoints.length >= 1"
                  :cx="activePolygonPoints[0][0] * imgNaturalWidth"
                  :cy="activePolygonPoints[0][1] * imgNaturalHeight"
                  class="svg-first-point-pulse"
                  @click.stop="finishDrawing"
                  title="点击首点闭合多边形"
                />
                <!-- 绘制的控制点圆圈 -->
                <circle
                  v-for="(pt, ptIndex) in activePolygonPoints"
                  :key="'draw-pt-' + ptIndex"
                  :cx="pt[0] * imgNaturalWidth"
                  :cy="pt[1] * imgNaturalHeight"
                  :r="ptIndex === 0 ? 4.5 : 2.0"
                  :class="{ 'first-draw-point': ptIndex === 0 }"
                  :style="ptIndex === 0 ? 'fill: #10b981; stroke: #ffffff; stroke-width: 1.5px; cursor: pointer;' : 'fill: rgba(99, 102, 241, 0.7); stroke: #ffffff; stroke-width: 1px;'"
                  @click.stop="ptIndex === 0 ? finishDrawing() : null"
                  :title="ptIndex === 0 ? '点击闭合多边形' : ''"
                />
              </g>

              <!-- 4. SAM 辅助模式下：渲染交互正/负打点以及自动识别预览 -->
              <g v-if="activeTool === 'sam'">
                <!-- SAM 预测预览多边形（动态流动虚线效果，动态适配填充透明度） -->
                <polygon
                  v-if="samPreviewPolygon"
                  :points="samPreviewPolygon.map(pt => `${pt[0] * imgNaturalWidth},${pt[1] * imgNaturalHeight}`).join(' ')"
                  class="svg-sam-preview"
                  :style="{ fillOpacity: Math.max(polyFillOpacity, 0.35) }"
                />
                
                <!-- 渲染用户的正负提示点 -->
                <circle
                  v-for="(prompt, idx) in samPrompts"
                  :key="'prompt-' + idx"
                  :cx="prompt.x"
                  :cy="prompt.y"
                  r="2.5"
                  class="prompt-dot"
                  :class="prompt.label === 1 ? 'positive' : 'negative'"
                  :title="prompt.label === 1 ? '前景正点' : '背景负点'"
                />
              </g>

              <!-- 5. 橡皮擦涂抹范围指示器 -->
              <circle
                v-if="eraserMousePos && (activeTool === 'eraser' || (activeTool === 'edit' && altPressed))"
                :cx="eraserMousePos[0]"
                :cy="eraserMousePos[1]"
                :r="eraserRadius"
                class="svg-eraser-pointer"
              />

              <!-- 6. 多边形轮廓中心数字编号徽章 (与右侧分类标签管理/图像实例严格对应) -->
              <g
                v-for="(poly, polyIndex) in polygons"
                v-show="!poly.hidden"
                :key="'poly-badge-' + polyIndex"
                class="svg-poly-badge"
                :class="{ active: activePolyIndex === polyIndex }"
                :transform="`translate(${getPolygonCenter(poly.points)[0]}, ${getPolygonCenter(poly.points)[1]})`"
                @click.stop="selectPolygon(polyIndex)"
                @mousedown.stop
                :title="`#${polyIndex + 1} (${classes[poly.class_id] || '默认'}) - 点击选中`"
              >
                <!-- 胶囊状背景徽章 -->
                <rect
                  :x="-getBadgeDimensions('#' + (polyIndex + 1)).width / 2"
                  :y="-getBadgeDimensions('#' + (polyIndex + 1)).height / 2"
                  :width="getBadgeDimensions('#' + (polyIndex + 1)).width"
                  :height="getBadgeDimensions('#' + (polyIndex + 1)).height"
                  :rx="getBadgeDimensions('#' + (polyIndex + 1)).rx"
                  class="poly-badge-bg"
                  :style="{
                    fill: getPolyColor(poly.class_id),
                    stroke: activePolyIndex === polyIndex ? '#ffffff' : getPolyColor(poly.class_id),
                    strokeWidth: `${getBadgeDimensions('#' + (polyIndex + 1)).strokeWidth}px`
                  }"
                />
                <!-- 数字文本 -->
                <text
                  class="poly-badge-text"
                  :style="{ fontSize: `${getBadgeDimensions('#' + (polyIndex + 1)).fontSize}px` }"
                  text-anchor="middle"
                  dominant-baseline="central"
                >
                  #{{ polyIndex + 1 }}
                </text>
              </g>
            </svg>

            <!-- 7. 编辑模式下：选中的多边形实例上方悬浮操作条 (Floating Bubble Action Bar) -->
            <transition name="popover-fade">
              <div 
                v-if="activeTool === 'edit' && activePolyIndex !== null && polygons[activePolyIndex] && !polygons[activePolyIndex].hidden && activePolyFloatingPos"
                class="instance-floating-bar"
                :style="{
                  left: `${activePolyFloatingPos.x}px`,
                  top: `${activePolyFloatingPos.y}px`,
                  transform: `translate(-50%, -100%) scale(${1 / zoom})`
                }"
                @mousedown.stop
                @click.stop
              >
                <div class="floating-bar-content">
                  <!-- 1. 纯数字序号徽章 (不显示冗长类别名) -->
                  <span class="floating-bar-title" :style="{ color: getPolyColor(polygons[activePolyIndex].class_id) }">
                    #{{ activePolyIndex + 1 }}
                  </span>

                  <!-- 2. 当前选中实例 SAM 优化按钮 (仅保留星星图标) -->
                  <button 
                    class="floating-refine-btn" 
                    :disabled="isRefiningSingleIndex === activePolyIndex || isRefiningAll"
                    @click="refineSinglePolygon(activePolyIndex)"
                    title="使用 SAM 重新高精贴合此实例边缘 (快捷键 Ctrl+R)"
                  >
                    <span v-if="isRefiningSingleIndex === activePolyIndex" class="spinner" style="width: 10px; height: 10px; margin-right: 3px;"></span>
                    <span v-else style="font-size: 11px; margin-right: 2px;">✨</span>
                    <span>{{ isRefiningSingleIndex === activePolyIndex ? '优化中...' : 'SAM优化' }}</span>
                  </button>

                  <!-- 3. 全图所有实例 SAM 优化全部按钮 (仅保留星星图标) -->
                  <button 
                    class="floating-refine-btn all-btn" 
                    :disabled="isRefiningAll || isRefiningSingleIndex !== null || polygons.length === 0"
                    @click="refineAllPolygons"
                    :title="`使用 SAM 批量重新优化全图所有 ${polygons.length} 个实例边缘`"
                  >
                    <span v-if="isRefiningAll" class="spinner" style="width: 10px; height: 10px; margin-right: 3px;"></span>
                    <span v-else style="font-size: 11px; margin-right: 2px;">✨</span>
                    <span>{{ isRefiningAll ? '批量优化中...' : 'SAM优化全部' }}</span>
                  </button>

                  <!-- 4. 实例删除快捷按钮 -->
                  <button 
                    class="floating-delete-btn"
                    @click="deletePolygon(activePolyIndex)"
                    title="删除此实例 (Delete / Backspace)"
                  >
                    <svg style="width: 12px; height: 12px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                    </svg>
                  </button>
                </div>
                <div class="floating-bar-arrow"></div>
              </div>
            </transition>

          </div>

          <!-- 缩放指示器 -->

          <div v-if="currentImage" class="zoom-indicator">
            Zoom: {{ Math.round(zoom * 100) }}% | W:{{ imgNaturalWidth }} H:{{ imgNaturalHeight }}
          </div>
        </div>
      </div>

      <!-- 3. 右栏：类别与实例管理 -->
      <div class="glass-card right-sidebar-card">
        <!-- 类别定义 -->
        <div class="class-list-container">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <span style="font-weight: 600; font-size: 14px; color: var(--text-primary);">分类标签管理</span>
            <button class="console-btn" @click="addClass" style="font-size: 11px; padding: 2px 6px;">+ 新增</button>
          </div>
          <div class="class-badge-group">
            <div
              v-for="(clsName, idx) in classes"
              :key="idx"
              class="class-badge"
              :class="{ active: activeClassIndex === idx }"
              @click="activeClassIndex = idx"
              style="position: relative; display: flex; align-items: center; padding-right: 24px;"
            >
              <span :style="{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: getPolyColor(idx), marginRight: '6px' }"></span>
              {{ clsName }}
              <span 
                v-if="classes.length > 1"
                class="class-delete-icon" 
                @click.stop="removeClass(idx)"
                title="删除此类别"
              >
                ×
              </span>
            </div>
          </div>
        </div>

        <!-- 当前标注实例列表 -->
        <div class="section-title" style="margin-bottom: 12px; font-size: 14px; border-left-color: var(--success);">
          当前图像实例 ({{ polygons.length }})
        </div>

        <div class="instance-list-container">
          <div v-if="polygons.length === 0" style="text-align: center; color: var(--text-muted); font-size: 13px; margin-top: 30px;">
            暂无标注多边形
          </div>
          <div
            v-for="(poly, idx) in polygons"
            :key="'inst-' + idx"
            :id="'inst-item-' + idx"
            class="instance-item"
            :class="{ active: activePolyIndex === idx }"
            @click="selectPolygon(idx)"
          >
            <div class="instance-label">
              <span class="instance-color-box" :style="{ background: getPolyColor(poly.class_id) }"></span>
              <span style="font-weight: 500;">#{{ idx + 1 }}</span>
              <select v-model.number="poly.class_id" style="padding: 2px 4px; font-size: 11px; width: 70px; border-radius: 4px; height: 24px;" @click.stopPropagation>
                <option v-for="(clsName, clsIdx) in classes" :key="clsIdx" :value="clsIdx">
                  {{ clsName }}
                </option>
              </select>
            </div>
            
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">{{ poly.points.length }} pts</span>
              
              <!-- 显隐眼睛图标按钮 -->
              <button 
                class="instance-visibility-btn" 
                :class="{ hidden: poly.hidden }"
                @click.stop="togglePolygonVisibility(idx)" 
                :title="poly.hidden ? '显示此实例' : '隐藏此实例并防止误触'"
              >
                <svg v-if="!poly.hidden" style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else style="width: 14px; height: 14px; color: var(--text-muted);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              </button>

              <div style="position: relative; display: inline-flex; align-items: center;">

                <transition name="delete-tooltip-fade">
                  <div 
                    v-if="pendingDeletePolyIndex === idx" 
                    class="delete-confirm-tooltip"
                    @click.stop="handleDeleteClick(idx)"
                  >
                    再次点击删除
                  </div>
                </transition>
                <button 
                  class="file-delete-btn" 
                  :class="{ 'pending-delete': pendingDeletePolyIndex === idx }"
                  style="opacity: 1;" 
                  @click.stop="handleDeleteClick(idx)" 
                  :title="pendingDeletePolyIndex === idx ? '再次点击确认删除' : '点击删除此多边形'"
                >
                  <svg style="width: 14px; height: 14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 快捷操作区 -->
        <div style="margin-top: 16px; border-top: 1px solid var(--border-color); padding-top: 16px;">
          <!-- 键盘快捷键引导 -->
          <div style="font-size: 11px; color: var(--text-muted); line-height: 1.5;">
            <div>⌨️ <strong>快捷键引导：</strong></div>
            <div>• <kbd>Ctrl+Z</kbd> : 手动标注未闭合时逐点撤销</div>
            <div>• <kbd>Ctrl+R</kbd> : 编辑模式使用 SAM 重新优化选中实例边缘</div>
            <div>• <kbd>Enter</kbd> : 闭合手动连线 / 确认SAM生成</div>
            <div>• <kbd>Esc</kbd> : 取消手动连线 / 撤销SAM的点击点</div>
            <div>• <kbd>Delete / Backspace</kbd> : 删除选中的多边形</div>
            <div>• <kbd>空格键</kbd> : 按住后左键拖拽可随时平移画布</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';

// 动态检测后端接口，开发环境指向 9523，生产环境同源
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:9523'
  : window.location.origin;

// 状态文字映射表
const stateLabels = {
  idle: '等待训练',
  preparing: '正在准备数据集（数据划分）',
  training: 'YOLO 训练进行中',
  completed: '训练成功结束',
  failed: '训练异常退出',
  stopped: '已手动终止训练'
};

// ==========================================
// 全局 Toast 轻提示系统逻辑
// ==========================================
const toasts = ref([]);
let toastIdCount = 0;

const showToast = (message, type = 'info') => {
  const id = toastIdCount++;
  toasts.value.push({ id, message, type });
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id);
  }, 3000);
};

// ==========================================
// 1. 训练控制台状态与逻辑
// ==========================================

const currentTab = ref('train'); // train | label
const isDark = ref(true); // 默认暗色模式

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

const trainStatus = reactive({
  state: 'idle',
  dataset: '',
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
  },
  last_run: {
    has_data: false,
    dataset: '',
    has_best_weight: false,
    metrics: {
      epoch: 0,
      box_loss: 0.0,
      seg_loss: 0.0,
      cls_loss: 0.0,
      map50: 0.0,
      map50_95: 0.0
    },
    meta: {},
    results_png: ''
  }
});

const logs = ref([]);
const consoleRef = ref(null);
let statusInterval = null;
let sysInfoInterval = null;
let eventSource = null;

const isTraining = computed(() => {
  return trainStatus.state === 'training' || trainStatus.state === 'preparing';
});

const fetchSysInfo = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/sysinfo?dataset=${currentDataset.value}`);
    if (res.ok) {
      const data = await res.json();
      Object.assign(sysInfo, data);
    }
  } catch (err) {
    console.error('获取系统状态失败:', err);
  }
};

const fetchTrainStatus = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (res.ok) {
      const data = await res.json();
      Object.assign(trainStatus, data);
      
      if (isTraining.value && !eventSource) {
        startLogStream();
      }
      if (!isTraining.value && eventSource) {
        closeLogStream();
      }
    }
  } catch (err) {
    console.error('获取训练状态失败:', err);
  }
};

const downloadBestWeight = () => {
  window.open(`${API_BASE}/api/download_best`, '_blank');
};

const getResultsPngUrl = (path) => {
  if (!path) return '';
  return `${API_BASE}${path}?t=${new Date().getTime()}`;
};

const startLogStream = () => {
  if (eventSource) return;
  console.log('启动 SSE 实时日志接收...');
  eventSource = new EventSource(`${API_BASE}/api/logs`);
  eventSource.onmessage = (event) => {
    if (event.data.trim()) {
      logs.value.push(event.data);
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

const closeLogStream = () => {
  if (eventSource) {
    console.log('关闭 SSE 实时日志接收...');
    eventSource.close();
    eventSource = null;
  }
};

const handleStartTrain = async () => {
  try {
    clearLogs();
    
    // 统计未标注的图片并提示
    try {
      const imgRes = await fetch(`${API_BASE}/api/labeling/images?dataset=${currentDataset.value}`);
      if (imgRes.ok) {
        const list = await imgRes.json();
        const unlabeledCount = list.filter(img => img.status === "unlabeled").length;
        if (unlabeledCount > 0) {
          if (!confirm(`尚有 ${unlabeledCount} 张图片未标注，未标注的图片将作为背景训练。是否继续？`)) {
            logs.value.push('[SYSTEM] 训练启动已被取消。');
            return;
          }
        }
      }
    } catch (err) {
      console.error('获取待标图片列表失败:', err);
    }

    showToast('正在向后端请求启动 YOLO 训练...', 'info');
    logs.value.push('[SYSTEM] 正在向后端请求启动 YOLO26s-seg 实例分割训练...');
    const res = await fetch(`${API_BASE}/api/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, dataset: currentDataset.value })
    });
    if (res.ok) {
      const data = await res.json();
      logs.value.push('[SYSTEM] ' + data.message);
      showToast('训练已成功拉起！', 'success');
      startLogStream();
      fetchTrainStatus();
    } else {
      const errData = await res.json();
      logs.value.push(`[SYSTEM] 启动训练失败: ${errData.detail || '未知网络错误'}`);
      showToast('启动训练失败: ' + (errData.detail || '错误'), 'error');
    }
  } catch (err) {
    logs.value.push(`[SYSTEM] 网络连通错误: ${err.message}`);
    showToast('无法连接到训练服务器', 'error');
  }
};

const handleStopTrain = async () => {
  if (!confirm('警告：确定要强行中止当前正在运行的训练任务吗？')) return;
  try {
    logs.value.push('[SYSTEM] 正在发送中止信号...');
    const res = await fetch(`${API_BASE}/api/stop`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      logs.value.push('[SYSTEM] ' + data.message);
      showToast('训练已手动中止', 'warning');
      closeLogStream();
      fetchTrainStatus();
    } else {
      const errData = await res.json();
      logs.value.push(`[SYSTEM] 停止训练请求失败: ${errData.detail}`);
      showToast('中止失败: ' + errData.detail, 'error');
    }
  } catch (err) {
    logs.value.push(`[SYSTEM] 无法连接到服务器进行终止: ${err.message}`);
    showToast('网络连接异常，请重试', 'error');
  }
};

const clearLogs = () => { logs.value = []; };
const scrollToBottom = () => {
  nextTick(() => {
    if (consoleRef.value) {
      consoleRef.value.scrollTop = consoleRef.value.scrollHeight;
    }
  });
};

// 主题切换
const toggleTheme = () => {
  isDark.value = !isDark.value;
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light');
  updateThemeClass();
};

const updateThemeClass = () => {
  if (isDark.value) {
    document.documentElement.classList.add('dark-theme');
  } else {
    document.documentElement.classList.remove('dark-theme');
  }
};

// ==========================================
// 2. 数据标注平台状态与核心逻辑
// ==========================================

const imageList = ref([]);
const searchQuery = ref('');
const filterStatus = ref('unlabeled'); // labeled | unlabeled | negative
const currentImage = ref(null);
const activeTool = ref('edit'); // edit | draw | sam | pan | eraser

// 橡皮擦相关状态
const eraserRadius = ref(20); // 橡皮擦半径，单位像素
const isErasing = ref(false); // 是否正在擦除
const altPressed = ref(false); // Alt 键是否被按下
const eraserMousePos = ref(null); // 橡皮擦鼠标坐标 [x, y]

// 类别、多边形与模型列表
const classes = ref(['pig']);
const activeClassIndex = ref(0);
const polygons = ref([]);
const activePolyIndex = ref(null);
const pendingDeletePolyIndex = ref(null);
let pendingDeleteTimer = null;
const modelsList = ref([]); // 后端扫描出的 YOLO-seg 模型列表
const selectedModelPath = ref(''); // 当前选中的模型路径
const showModelPopover = ref(false); // 控制模型识别 Popover 的显隐
const isAutoDetectAndRefining = ref(false); // 是否处于“识别并优化”执行中

const toggleModelPopover = () => {
  showModelPopover.value = !showModelPopover.value;
  if (showModelPopover.value) {
    showPromptPopover.value = false;
    if (!selectedModelPath.value && modelsList.value.length > 0) {
      selectedModelPath.value = modelsList.value[0].path;
    }
  }
};

const closeModelPopoverOnOutside = (e) => {
  if (showModelPopover.value) {
    const el = document.querySelector('.model-popover-wrapper');
    if (el && !el.contains(e.target)) {
      showModelPopover.value = false;
    }
  }
};

// 拖拽与缩水平移状态
const zoom = ref(1.0);
const panX = ref(0);
const panY = ref(0);
const imgNaturalWidth = ref(800);
const imgNaturalHeight = ref(600);

const spacePressed = ref(false);
const rightMouseDown = ref(false);
const panStart = ref({ x: 0, y: 0 });
const isPanning = ref(false);

const uploadInputRef = ref(null);

// 手动绘制临时点
const activePolygonPoints = ref([]); // 归一化坐标列表
const mousePos = ref(null); // 绝对像素坐标点

// SAM 预测交互点与预览
const samPrompts = ref([]); // {x, y, label} 绝对像素点
const samPreviewPolygon = ref(null); // 归一化坐标点数组
const isAutoDetecting = ref(false);
const isSamPredicting = ref(false);

// SAM 边缘重分割优化状态
const isRefiningSingleIndex = ref(null);
const isRefiningAll = ref(false);

// 计算当前选中的多边形顶部悬浮条位置（图片原始像素坐标）
const activePolyFloatingPos = computed(() => {
  if (activePolyIndex.value === null || !polygons.value[activePolyIndex.value]) return null;
  const poly = polygons.value[activePolyIndex.value];
  if (!poly.points || poly.points.length === 0) return null;
  
  const w = imgNaturalWidth.value || 800;
  const h = imgNaturalHeight.value || 600;
  
  let minY = Infinity;
  let minX = Infinity;
  let maxX = -Infinity;
  
  for (const pt of poly.points) {
    const px = pt[0] * w;
    const py = pt[1] * h;
    if (py < minY) minY = py;
    if (px < minX) minX = px;
    if (px > maxX) maxX = px;
  }
  
  const centerX = (minX + maxX) / 2;
  // 留出 8px 的向上安全间距（在缩放环境下转换为原始图像像素距离）
  const topY = Math.max(0, minY - 8 / (zoom.value || 1.0));
  
  return { x: centerX, y: topY };
});

// Prompt 开放词汇识别
const promptText = ref('pig');

const promptConf = ref(0.01); // 默认 0.01 置信度，最大化捕获全图目标
const isPromptDetecting = ref(false);
const showPromptPopover = ref(false);

const togglePromptPopover = () => {
  showPromptPopover.value = !showPromptPopover.value;
  if (showPromptPopover.value) {
    showModelPopover.value = false;
  }
};

const closePromptPopoverOnOutside = (e) => {
  if (showPromptPopover.value) {
    const el = document.querySelector('.prompt-popover-wrapper');
    if (el && !el.contains(e.target)) {
      showPromptPopover.value = false;
    }
  }
};


// 多边形填充不透明度 (0.1 ~ 0.8，默认 0.35)
const polyFillOpacity = ref(0.35);

// 颜色映射系统 (采用高对比度、极其鲜艳高亮的对比色系，避免浅暗绿混淆)
const colors = ['#6366f1', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#8b5cf6', '#3b82f6', '#10b981', '#f43f5e'];
const getPolyColor = (classId) => {
  return colors[classId % colors.length];
};

// 数据集管理状态
const datasets = ref([]);
const currentDataset = ref('default');

const fetchDatasets = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/labeling/datasets`);
    if (res.ok) {
      const data = await res.json();
      datasets.value = data.datasets || [];
      if (datasets.value.length > 0 && !datasets.value.includes(currentDataset.value)) {
        currentDataset.value = datasets.value[0];
      }
    }
  } catch (err) {
    console.error('获取数据集列表失败:', err);
  }
};

const handleCreateDataset = async () => {
  const name = prompt('请输入新数据集的名称（仅限中文、字母、数字、下划线和连字符）：');
  if (name && name.trim()) {
    const trimmed = name.trim();
    if (!/^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$/.test(trimmed)) {
      showToast('数据集名称格式不正确，只能包含中文、字母、数字、下划线和连字符', 'error');
      return;
    }
    
    try {
      const res = await fetch(`${API_BASE}/api/labeling/datasets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed })
      });
      
      if (res.ok) {
        showToast(`数据集 [${trimmed}] 创建成功！`, 'success');
        await fetchDatasets();
        currentDataset.value = trimmed;
      } else {
        const err = await res.json();
        showToast('创建数据集失败: ' + (err.detail || '接口错误'), 'error');
      }
    } catch (err) {
      console.error('创建数据集出错:', err);
      showToast('连接服务器失败', 'error');
    }
  }
};

// 类别级联删除方法
const removeClass = async (idx) => {
  const clsName = classes.value[idx];
  if (classes.value.length <= 1) {
    showToast('必须保留至少一个分类标签', 'warning');
    return;
  }
  
  if (!confirm(`确定要删除类别标签 [${clsName}] 吗？\n\n警告：删除后该数据集下所有图片的此类别标注将被自动清除，其他类别索引会自动前移。此操作不可逆！`)) {
    return;
  }
  
  // 1. 本地调整
  classes.value.splice(idx, 1);
  polygons.value = polygons.value
    .filter(p => p.class_id !== idx)
    .map(p => {
      if (p.class_id > idx) {
        return { ...p, class_id: p.class_id - 1 };
      }
      return p;
    });
    
  if (activeClassIndex.value >= classes.value.length) {
    activeClassIndex.value = classes.value.length - 1;
  } else if (activeClassIndex.value === idx) {
    activeClassIndex.value = 0;
  } else if (activeClassIndex.value > idx) {
    activeClassIndex.value -= 1;
  }
  
  // 2. 发送后端
  try {
    const res = await fetch(`${API_BASE}/api/labeling/classes?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ classes: classes.value })
    });
    
    if (res.ok) {
      showToast(`已成功删除类别标签: ${clsName}，后端已完成级联标注清理。`, 'success');
      if (currentImage.value) {
        await selectImage(currentImage.value);
      }
    } else {
      showToast('删除类别失败', 'error');
    }
  } catch (err) {
    console.error('删除类别出错:', err);
    showToast('无法连接服务器', 'error');
  }
};

const fetchClasses = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/labeling/classes?dataset=${currentDataset.value}`);
    if (res.ok) {
      const data = await res.json();
      classes.value = data.classes || ['pig'];
      // 校验并防止 activeClassIndex 越界
      if (activeClassIndex.value >= classes.value.length || activeClassIndex.value < 0) {
        activeClassIndex.value = 0;
      }
    }
  } catch (err) {
    console.error('获取类别列表失败:', err);
  }
};

// 监听当前数据集变化，重置分类选中并重载相关列表
watch(currentDataset, async () => {
  activeClassIndex.value = 0; // 切换数据集时默认选中第一个分类标签
  await fetchImageList();
  await fetchClasses();
  currentImage.value = null;
  polygons.value = [];
  activePolyIndex.value = null;
  await fetchSysInfo();
});

// 图片源 URL
const currentImageSrc = computed(() => {
  if (!currentImage.value) return '';
  return `${API_BASE}/labeling_images/${currentDataset.value}/images/${currentImage.value.name}?t=${currentImage.value.mtime}`;
});

// 筛选后的图片列表
const filteredImageList = computed(() => {
  let list = imageList.value;
  if (filterStatus.value === 'labeled') {
    list = list.filter(img => img.status === 'labeled');
  } else if (filterStatus.value === 'unlabeled') {
    list = list.filter(img => img.status === 'unlabeled');
  } else if (filterStatus.value === 'negative') {
    list = list.filter(img => img.status === 'negative');
  }
  if (!searchQuery.value) return list;
  const q = searchQuery.value.toLowerCase();
  return list.filter(img => img.name.toLowerCase().includes(q));
});

// 获取待标图片列表
const fetchImageList = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/labeling/images?dataset=${currentDataset.value}`);
    if (res.ok) {
      imageList.value = await res.json();
    }
  } catch (err) {
    console.error('获取图片列表失败:', err);
  }
};

// 获取可用检测模型列表
const fetchModelsList = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/labeling/models`);
    if (res.ok) {
      modelsList.value = await res.json();
      if (modelsList.value.length > 0 && !selectedModelPath.value) {
        selectedModelPath.value = modelsList.value[0].path;
      }
    }
  } catch (err) {
    console.error('获取权重列表失败:', err);
  }
};


// 选定并加载某张图片的数据
const selectImage = async (img) => {
  currentImage.value = img;
  polygons.value = [];
  activePolyIndex.value = null;
  activePolygonPoints.value = [];
  samPrompts.value = [];
  samPreviewPolygon.value = null;
  
  try {
    const res = await fetch(`${API_BASE}/api/labeling/labels/${img.name}?dataset=${currentDataset.value}`);
    if (res.ok) {
      const data = await res.json();
      classes.value = data.classes || ['pig'];
      if (activeClassIndex.value >= classes.value.length || activeClassIndex.value < 0) {
        activeClassIndex.value = 0;
      }
      polygons.value = data.polygons || [];
    }
  } catch (err) {
    console.error('加载标注失败:', err);
  }
};

// 图像加载完成获取实际分辨率，并自适应容器宽高进行缩放和居中
const onImageLoad = (e) => {
  const imgW = e.target.naturalWidth || 800;
  const imgH = e.target.naturalHeight || 600;
  imgNaturalWidth.value = imgW;
  imgNaturalHeight.value = imgH;
  
  const workspace = document.querySelector('.canvas-workspace');
  if (workspace) {
    // 留出 16 像素的安全边距
    const pad = 16;
    const containerW = Math.max(100, workspace.clientWidth - pad * 2);
    const containerH = Math.max(100, workspace.clientHeight - pad * 2);
    
    // 计算缩放比，使图片完整包容在容器内
    const scaleX = containerW / imgW;
    const scaleY = containerH / imgH;
    let bestScale = Math.min(scaleX, scaleY);
    
    // 限制缩放区间：最小 5%，最大 150%（不强行把超小图拉得太大）
    bestScale = Math.max(0.05, Math.min(1.5, bestScale));
    zoom.value = bestScale;
    
    // 计算居中对齐时的平移位置（由于 .canvas-container 已被 left:0; top:0; 绝对定位化）
    panX.value = (workspace.clientWidth - imgW * bestScale) / 2;
    panY.value = (workspace.clientHeight - imgH * bestScale) / 2;
  } else {
    zoom.value = 1.0;
    panX.value = 0;
    panY.value = 0;
  }
};



// 设置当前使用工具
const setTool = (tool) => {
  activeTool.value = tool;
  activePolyIndex.value = null;
  activePolygonPoints.value = [];
  samPrompts.value = [];
  samPreviewPolygon.value = null;
  isErasing.value = false;
  eraserMousePos.value = null;
};

// ==========================================
// 3. 画布事件（Pan & Zoom 缩放和平移）
// ==========================================

const handleZoom = (e) => {
  if (!currentImage.value) return;
  const zoomFactor = 1.1;
  const oldZoom = zoom.value;
  
  if (e.deltaY < 0) {
    zoom.value = Math.min(8.0, oldZoom * zoomFactor);
  } else {
    zoom.value = Math.max(0.15, oldZoom / zoomFactor);
  }
  
  const container = e.currentTarget.querySelector('.canvas-container');
  if (container) {
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    const imgX = (mouseX - panX.value) / oldZoom;
    const imgY = (mouseY - panY.value) / oldZoom;
    
    panX.value = mouseX - imgX * zoom.value;
    panY.value = mouseY - imgY * zoom.value;
  }
};

const startPan = (e) => {
  if (!currentImage.value) return;
  
  // 在 SAM 辅助模式下，鼠标右键（e.button === 2）专门用于添加背景点，不触发平移
  if (activeTool.value === 'sam' && e.button === 2) {
    return;
  }
  
  if (activeTool.value === 'pan' || spacePressed.value || e.button === 2) {
    e.preventDefault();
    isPanning.value = true;
    if (e.button === 2) {
      rightMouseDown.value = true;
    }
    
    panStart.value = {
      x: e.clientX - panX.value,
      y: e.clientY - panY.value
    };
    
    window.addEventListener('mousemove', handlePan);
    window.addEventListener('mouseup', stopPan);
  }
};

const handlePan = (e) => {
  if (!isPanning.value) return;
  panX.value = e.clientX - panStart.value.x;
  panY.value = e.clientY - panStart.value.y;
};

const stopPan = (e) => {
  isPanning.value = false;
  rightMouseDown.value = false;
  window.removeEventListener('mousemove', handlePan);
  window.removeEventListener('mouseup', stopPan);
};

// ==========================================
// 4. SVG 画布坐标转换与标注绘制交互
// ==========================================

const getSVGCoords = (e) => {
  const svg = document.querySelector('.svg-overlay');
  if (!svg) return [0, 0];
  const rect = svg.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * imgNaturalWidth.value;
  const y = ((e.clientY - rect.top) / rect.height) * imgNaturalHeight.value;
  return [x, y];
};

const handleSVGMouseDown = (e) => {
  // 如果按住空格键或者正处于平移状态，拒绝右键打点
  if (spacePressed.value || isPanning.value || activeTool.value === 'pan') return;
  
  if (e.button === 2 && activeTool.value === 'sam') {
    e.stopPropagation();
    const [x, y] = getSVGCoords(e);
    samPrompts.value.push({ x, y, label: 0 }); // 0: 负点（背景）
    triggerSAMPredict();
    return;
  }

  // 橡皮擦左键涂抹
  if (e.button === 0 && (activeTool.value === 'eraser' || (activeTool.value === 'edit' && altPressed.value))) {
    e.stopPropagation();
    e.preventDefault();
    if (activePolyIndex.value === null) {
      showToast('请先在右侧列表或画布中选择一个多边形实例再进行擦除', 'warning');
      return;
    }
    isErasing.value = true;
    const [x, y] = getSVGCoords(e);
    erasePointsAt(x, y);
    
    window.addEventListener('mouseup', stopErasingGlobal);
  }
};

const handleSVGClick = (e) => {
  if (!currentImage.value) return;
  
  // 如果正在按住空格键移动画面、处于手形模式、或者刚刚结束拖曳平移，拒绝打点
  if (spacePressed.value || activeTool.value === 'pan' || isPanning.value) {
    return;
  }
  
  if (activeTool.value === 'draw' && e.button === 0) {
    const [px, py] = getSVGCoords(e);
    const normX = px / imgNaturalWidth.value;
    const normY = py / imgNaturalHeight.value;
    
    if (activePolygonPoints.value.length >= 3) {
      const first = activePolygonPoints.value[0];
      const firstX = first[0] * imgNaturalWidth.value;
      const firstY = first[1] * imgNaturalHeight.value;
      const distImg = Math.hypot(px - firstX, py - firstY);
      
      // 判定屏幕上的物理像素距离。当点击位置与第一个点的屏幕距离小于 8 像素时，判定为闭合
      if (distImg * zoom.value < 8) {
        finishDrawing();
        return;
      }
    }

    
    activePolygonPoints.value.push([normX, normY]);
  }
  
  else if (activeTool.value === 'sam' && e.button === 0) {
    const [x, y] = getSVGCoords(e);
    samPrompts.value.push({ x, y, label: 1 }); // 1: 正点（前景）
    triggerSAMPredict();
  }
};

const updateMousePos = (e) => {
  const [x, y] = getSVGCoords(e);
  if (activeTool.value === 'draw' && activePolygonPoints.value.length > 0) {
    mousePos.value = [x, y];
  } else {
    mousePos.value = null;
  }

  if (activeTool.value === 'eraser' || (activeTool.value === 'edit' && altPressed.value)) {
    eraserMousePos.value = [x, y];
  } else {
    eraserMousePos.value = null;
  }
};

const finishDrawing = () => {
  if (activePolygonPoints.value.length >= 3) {
    polygons.value.push({
      class_id: activeClassIndex.value,
      points: [...activePolygonPoints.value]
    });
  }
  activePolygonPoints.value = [];
};

// 手动打点模式下撤销未闭合多边形的最新顶点（逐点撤销直至清空）
const undoLastDrawPoint = () => {
  if (activeTool.value !== 'draw') return;
  if (!activePolygonPoints.value || activePolygonPoints.value.length === 0) return;

  activePolygonPoints.value.pop();

  // 如果撤销至最后一个点导致点集清空，同步重置鼠标辅助线坐标
  if (activePolygonPoints.value.length === 0) {
    mousePos.value = null;
  }
};

// ==========================================
// 5. 多边形编辑模式 (拖拽与中点插入)
// ==========================================

// 计算多边形几何中心坐标（返回绝对像素坐标 [pixelX, pixelY]）
const getPolygonCenter = (points) => {
  if (!points || points.length === 0) return [0, 0];
  const w = imgNaturalWidth.value || 800;
  const h = imgNaturalHeight.value || 600;

  if (points.length === 1) {
    return [points[0][0] * w, points[0][1] * h];
  }
  if (points.length === 2) {
    return [
      ((points[0][0] + points[1][0]) / 2) * w,
      ((points[0][1] + points[1][1]) / 2) * h
    ];
  }

  // 多边形面积加权质心 (Centroid of Polygon)
  let area = 0;
  let cx = 0;
  let cy = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const factor = p1[0] * p2[1] - p2[0] * p1[1];
    area += factor;
    cx += (p1[0] + p2[0]) * factor;
    cy += (p1[1] + p2[1]) * factor;
  }
  area = area * 0.5;

  // 退化情况或计算无效时，使用算术平均顶点坐标降级
  if (Math.abs(area) < 1e-6 || isNaN(cx) || isNaN(cy)) {
    let sumX = 0;
    let sumY = 0;
    for (let i = 0; i < n; i++) {
      sumX += points[i][0];
      sumY += points[i][1];
    }
    return [(sumX / n) * w, (sumY / n) * h];
  }

  cx = cx / (6 * area);
  cy = cy / (6 * area);

  // 边界保护（确保中心点处于图片像素区域内）
  cx = Math.max(0, Math.min(1, cx));
  cy = Math.max(0, Math.min(1, cy));

  return [cx * w, cy * h];
};

// 计算多边形中心编号徽章的动态尺寸（自适应当前画布缩放与文本长度）
const getBadgeDimensions = (text) => {
  const currentZoom = zoom.value || 1.0;
  const height = 18 / currentZoom;
  const charWidth = 6.5 / currentZoom;
  const padding = 8 / currentZoom;
  const width = Math.max(height, text.length * charWidth + padding);
  const fontSize = 10 / currentZoom;
  const strokeWidth = 1.2 / currentZoom;
  return {
    width,
    height,
    rx: height / 2,
    fontSize,
    strokeWidth
  };
};

const selectPolygon = (idx) => {
  if (activeTool.value === 'draw' && activePolygonPoints.value.length > 0) {
    // 正在手动绘制打点中，不打断连线
    return;
  }
  if (activeTool.value === 'pan') {
    return;
  }
  if (activeTool.value !== 'eraser') {
    activeTool.value = 'edit';
  }
  activePolyIndex.value = idx;

  // 自动将右侧分类管理/实例列表中对应的项目平滑滚动至视口
  nextTick(() => {
    const el = document.getElementById(`inst-item-${idx}`);
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  });
};

const handlePolygonMouseDown = (e, polyIndex) => {
  if (e.button === 0) {
    if (activeTool.value === 'edit' || activeTool.value === 'eraser') {
      e.stopPropagation();
      selectPolygon(polyIndex);
    }
    
    if (activeTool.value === 'eraser') {
      e.preventDefault();
      isErasing.value = true;
      const [x, y] = getSVGCoords(e);
      erasePointsAt(x, y);
      window.addEventListener('mouseup', stopErasingGlobal);
    }
  }
};

const getPolygonLines = (poly) => {
  if (!poly || !poly.points || poly.points.length < 2) return [];
  const list = [];
  const pts = poly.points;
  for (let i = 0; i < pts.length; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % pts.length];
    list.push({
      index: i,
      x1: p1[0] * imgNaturalWidth.value,
      y1: p1[1] * imgNaturalHeight.value,
      x2: p2[0] * imgNaturalWidth.value,
      y2: p2[1] * imgNaturalHeight.value
    });
  }
  return list;
};

const insertPointOnEdge = (e, polyIndex, edgeIndex) => {
  const [px, py] = getSVGCoords(e);
  const normX = px / imgNaturalWidth.value;
  const normY = py / imgNaturalHeight.value;
  
  polygons.value[polyIndex].points.splice(edgeIndex + 1, 0, [normX, normY]);
  activePolyIndex.value = polyIndex;
  startDragPoint(e, polyIndex, edgeIndex + 1);
};

const dragInfo = ref(null);

const startDragPoint = (e, polyIndex, ptIndex) => {
  e.preventDefault();
  dragInfo.value = {
    polyIndex,
    ptIndex,
    startX: e.clientX,
    startY: e.clientY
  };
  window.addEventListener('mousemove', handleDragPoint);
  window.addEventListener('mouseup', stopDragPoint);
};

const handleDragPoint = (e) => {
  if (!dragInfo.value) return;
  const { polyIndex, ptIndex } = dragInfo.value;
  
  const [x, y] = getSVGCoords(e);
  const cx = Math.max(0, Math.min(imgNaturalWidth.value, x));
  const cy = Math.max(0, Math.min(imgNaturalHeight.value, y));
  
  polygons.value[polyIndex].points[ptIndex] = [
    cx / imgNaturalWidth.value,
    cy / imgNaturalHeight.value
  ];
};

const stopDragPoint = () => {
  dragInfo.value = null;
  window.removeEventListener('mousemove', handleDragPoint);
  window.removeEventListener('mouseup', stopDragPoint);
};

const erasePointsAt = (x, y) => {
  if (activePolyIndex.value === null || !polygons.value[activePolyIndex.value]) return;
  const poly = polygons.value[activePolyIndex.value];
  const radius = eraserRadius.value;
  
  const remainingPoints = poly.points.filter(pt => {
    const ptX = pt[0] * imgNaturalWidth.value;
    const ptY = pt[1] * imgNaturalHeight.value;
    const dist = Math.hypot(ptX - x, ptY - y);
    return dist > radius;
  });
  
  if (remainingPoints.length !== poly.points.length) {
    if (remainingPoints.length < 3) {
      deletePolygon(activePolyIndex.value);
      isErasing.value = false;
      showToast('多边形顶点已全部擦除，已自动删除该多边形', 'info');
    } else {
      polygons.value[activePolyIndex.value].points = remainingPoints;
    }
  }
};

const stopErasingGlobal = () => {
  isErasing.value = false;
  window.removeEventListener('mouseup', stopErasingGlobal);
};

const deletePoint = (polyIndex, ptIndex) => {
  if (polygons.value[polyIndex].points.length <= 3) {
    deletePolygon(polyIndex);
  } else {
    polygons.value[polyIndex].points.splice(ptIndex, 1);
  }
};

const handleDeleteClick = (idx) => {
  if (pendingDeletePolyIndex.value === idx) {
    // 再次点击（无论是两次慢速点击还是快速连续双击） -> 执行删除
    if (pendingDeleteTimer) {
      clearTimeout(pendingDeleteTimer);
      pendingDeleteTimer = null;
    }
    pendingDeletePolyIndex.value = null;
    deletePolygon(idx);
  } else {
    // 首次点击 -> 显示提示 Tooltip，并设置 3 秒超时自动隐藏
    if (pendingDeleteTimer) {
      clearTimeout(pendingDeleteTimer);
    }
    pendingDeletePolyIndex.value = idx;
    pendingDeleteTimer = setTimeout(() => {
      pendingDeletePolyIndex.value = null;
      pendingDeleteTimer = null;
    }, 3000);
  }
};

const deletePolygon = (idx) => {
  if (pendingDeletePolyIndex.value === idx) {
    pendingDeletePolyIndex.value = null;
    if (pendingDeleteTimer) {
      clearTimeout(pendingDeleteTimer);
      pendingDeleteTimer = null;
    }
  }
  polygons.value.splice(idx, 1);
  if (activePolyIndex.value === idx) {
    activePolyIndex.value = null;
  } else if (activePolyIndex.value > idx) {
    activePolyIndex.value--;
  }
};

const togglePolygonVisibility = (idx) => {
  const poly = polygons.value[idx];
  if (poly) {
    poly.hidden = !poly.hidden;
    if (poly.hidden && activePolyIndex.value === idx) {
      activePolyIndex.value = null;
    }
  }
};

const clearPolygons = () => {
  if (confirm('确认清空当前图片上的所有标注多边形吗？')) {
    polygons.value = [];
    activePolyIndex.value = null;
    showToast('已清空标注多边形', 'info');
  }
};

// ==========================================
// 6. 模型自动检测与 SAM 点击预测
// ==========================================

// 仅模型识别
const handleDetectOnly = async () => {
  if (!currentImage.value) {
    showToast('请先在左侧选择一张图片', 'warning');
    return;
  }
  if (!selectedModelPath.value) {
    showToast('请先选择一个分割权重模型', 'warning');
    return;
  }
  showModelPopover.value = false;
  await autoDetect(selectedModelPath.value);
};

// 模型识别并自动使用 SAM 优化全部
const handleDetectAndRefine = async () => {
  if (!currentImage.value) {
    showToast('请先在左侧选择一张图片', 'warning');
    return;
  }
  if (!selectedModelPath.value) {
    showToast('请先选择一个分割权重模型', 'warning');
    return;
  }
  
  const modelPath = selectedModelPath.value;
  const targetModel = modelsList.value.find(m => m.path === modelPath);
  const modelName = targetModel ? targetModel.name : modelPath;
  
  isAutoDetectAndRefining.value = true;
  showModelPopover.value = false;
  showToast(`正在加载【${modelName}】检测并准备 SAM 边缘优化...`, 'info');
  
  try {
    // 1. 调用模型检测
    const res = await fetch(`${API_BASE}/api/labeling/auto_detect?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        name: currentImage.value.name,
        model_path: modelPath
      })
    });
    
    if (!res.ok) {
      const err = await res.json();
      showToast('自动检测失败: ' + (err.detail || '模型加载出错'), 'error');
      return;
    }
    
    const data = await res.json();
    if (!data.polygons || data.polygons.length === 0) {
      showToast('未检测到任何目标实例', 'warning');
      setTool('edit'); // 识别完成默认切换到编辑模式
      return;
    }
    
    const currentTargetClass = activeClassIndex.value;
    const rawPolygons = data.polygons.map(poly => ({
      class_id: currentTargetClass,
      points: poly.points
    }));
    
    showToast(`已检测到 ${rawPolygons.length} 个实例，正在调用 SAM 进行全图边缘高清精修...`, 'info');
    
    // 2. 紧接着调用 SAM refine 全图优化
    const refineRes = await fetch(`${API_BASE}/api/labeling/sam_refine?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: currentImage.value.name,
        polygons: rawPolygons,
        padding: 0.03
      })
    });
    
    if (refineRes.ok) {
      const refineData = await refineRes.json();
      if (refineData.polygons && refineData.polygons.length > 0) {
        polygons.value = refineData.polygons;
        activePolyIndex.value = null;
        const targetClassName = classes.value[currentTargetClass] || `类别#${currentTargetClass + 1}`;
        showToast(`✨ 识别并 SAM 优化成功！共生成 ${refineData.polygons.length} 个高清实例，已应用【${targetClassName}】标签。`, 'success');
        setTool('edit'); // 识别并优化完成后默认切换到编辑模式，便于检查和调整
        return;
      }
    }
    
    // 若 SAM 优化接口未返回或异常，回退使用识别出的多边形
    polygons.value = rawPolygons;
    activePolyIndex.value = null;
    showToast(`模型检测成功（已生成 ${rawPolygons.length} 个实例），SAM 优化已跳过。`, 'info');
    setTool('edit'); // 默认切换到编辑模式，便于检查和调整
  } catch (err) {
    console.error('识别并优化出错:', err);
    showToast('连接识别或 SAM 服务异常', 'error');
  } finally {
    isAutoDetectAndRefining.value = false;
  }
};

const autoDetect = async (modelPath = null) => {
  if (!currentImage.value) return;
  isAutoDetecting.value = true;
  const targetModel = modelsList.value.find(m => m.path === modelPath);
  const modelName = targetModel ? targetModel.name : (modelPath || '分割模型');
  showToast(`正在加载【${modelName}】识别中...`, 'info');
  try {
    const res = await fetch(`${API_BASE}/api/labeling/auto_detect?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        name: currentImage.value.name,
        model_path: modelPath
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      if (data.polygons) {
        // 统一使用右侧“分类标签管理”中当前选中的类别 activeClassIndex.value
        const currentTargetClass = activeClassIndex.value;
        polygons.value = data.polygons.map(poly => ({
          ...poly,
          class_id: currentTargetClass
        }));
        activePolyIndex.value = null;
        const targetClassName = classes.value[currentTargetClass] || `类别#${currentTargetClass + 1}`;
        showToast(`自动识别成功！共检测到 ${data.polygons.length} 个实例，已应用当前选中的【${targetClassName}】标签。`, 'success');
      }
      setTool('edit'); // 模型识别完成后默认切换到编辑模式，便于检查和调整
    } else {
      const err = await res.json();
      showToast('自动检测失败: ' + (err.detail || '模型加载出错'), 'error');
    }
  } catch (err) {
    console.error(err);
    showToast('连接识别服务异常', 'error');
  } finally {
    isAutoDetecting.value = false;
  }
};


const promptDetect = async () => {
  if (!currentImage.value) {
    showToast('请先在左侧选择一张图片', 'warning');
    return;
  }
  const query = promptText.value.trim();
  if (!query) {
    showToast('请输入有效的识别 Prompt 提示词（如 pig）', 'warning');
    return;
  }

  isPromptDetecting.value = true;
  showToast(`正在通过 Prompt "${query}" 智能识别全图目标...`, 'info');
  try {
    const res = await fetch(`${API_BASE}/api/labeling/prompt_detect?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        name: currentImage.value.name,
        prompt: query,
        conf: promptConf.value,
        class_id: activeClassIndex.value
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      if (data.polygons && data.polygons.length > 0) {
        const currentTargetClass = activeClassIndex.value;
        const newPolys = data.polygons.map(poly => ({
          class_id: currentTargetClass,
          points: poly.points
        }));
        polygons.value = [...polygons.value, ...newPolys];
        activePolyIndex.value = null;
        const targetClassName = classes.value[currentTargetClass] || query;
        showToast(`✨ Prompt 识别成功！新增 ${data.polygons.length} 个实例，已标记为【${targetClassName}】`, 'success');
      } else {
        showToast(`未识别到符合提示词 "${query}" 的目标物体`, 'warning');
      }
      setTool('edit'); // Prompt 识别完成后默认切换到编辑模式，便于检查和调整
    } else {
      const err = await res.json();
      showToast('Prompt 识别失败: ' + (err.detail || '接口异常'), 'error');
    }
  } catch (err) {
    console.error(err);
    showToast('连接开放词汇识别服务异常', 'error');
  } finally {
    isPromptDetecting.value = false;
  }
};

const triggerSAMPredict = async () => {
  if (samPrompts.value.length === 0 || !currentImage.value) return;
  isSamPredicting.value = true;
  try {
    const res = await fetch(`${API_BASE}/api/labeling/sam_predict?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: currentImage.value.name,
        points: samPrompts.value.map(p => [p.x, p.y]),
        labels: samPrompts.value.map(p => p.label)
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      if (data.polygons && data.polygons.length > 0) {
        samPreviewPolygon.value = data.polygons[0];
      }
    } else {
      const err = await res.json();
      showToast('SAM 推理出错: ' + (err.detail || '未放置 SAM 权重'), 'error');
    }
  } catch (err) {
    console.error(err);
  } finally {
    isSamPredicting.value = false;
  }
};

const clearSAMPrompts = () => {
  samPrompts.value = [];
  samPreviewPolygon.value = null;
};

const confirmSAM = () => {
  if (!samPreviewPolygon.value) return;
  polygons.value.push({
    class_id: activeClassIndex.value,
    points: [...samPreviewPolygon.value]
  });
  samPrompts.value = [];
  samPreviewPolygon.value = null;
  showToast('SAM 实例已确认并创建', 'success');
};

// 优化单个多边形实例
const refineSinglePolygon = async (idx) => {
  if (!currentImage.value || idx === null || !polygons.value[idx]) return;
  const targetPoly = polygons.value[idx];
  if (!targetPoly.points || targetPoly.points.length < 3) {
    showToast('该多边形顶点过少，无法优化', 'warning');
    return;
  }
  
  isRefiningSingleIndex.value = idx;
  showToast(`正在通过 SAM 重新优化实例 #${idx + 1} 的边缘轮廓...`, 'info');
  
  try {
    const res = await fetch(`${API_BASE}/api/labeling/sam_refine?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: currentImage.value.name,
        polygons: [{
          class_id: targetPoly.class_id,
          points: targetPoly.points
        }],
        padding: 0.03
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      if (data.polygons && data.polygons.length > 0 && data.refined_count > 0) {
        polygons.value[idx].points = data.polygons[0].points;
        showToast(`✨ 实例 #${idx + 1} 已通过 SAM 优化完成！`, 'success');
      } else {
        showToast(`SAM 未能对实例 #${idx + 1} 产生更好边缘，已保留原标注`, 'warning');
      }
    } else {
      const err = await res.json();
      showToast('SAM 优化失败: ' + (err.detail || '接口错误'), 'error');
    }
  } catch (err) {
    console.error('SAM 优化请求异常:', err);
    showToast('连接 SAM 服务异常', 'error');
  } finally {
    isRefiningSingleIndex.value = null;
  }
};

// 批量优化全图所有多边形实例
const refineAllPolygons = async () => {
  if (!currentImage.value || polygons.value.length === 0) {
    showToast('当前没有标注项可供优化', 'warning');
    return;
  }
  
  isRefiningAll.value = true;
  showToast(`正在通过 SAM 批量优化全部 ${polygons.value.length} 个实例边缘...`, 'info');
  
  try {
    const res = await fetch(`${API_BASE}/api/labeling/sam_refine?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: currentImage.value.name,
        polygons: polygons.value.map(p => ({
          class_id: p.class_id,
          points: p.points
        })),
        padding: 0.03
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      if (data.polygons && data.polygons.length > 0) {
        for (let i = 0; i < data.polygons.length; i++) {
          if (polygons.value[i] && data.polygons[i].points) {
            polygons.value[i].points = data.polygons[i].points;
          }
        }
        showToast(`✨ 批量优化完毕！共成功精修 ${data.refined_count || data.polygons.length} 个实例边缘。`, 'success');
      }
    } else {
      const err = await res.json();
      showToast('批量优化失败: ' + (err.detail || '接口错误'), 'error');
    }
  } catch (err) {
    console.error('批量优化异常:', err);
    showToast('连接服务失败', 'error');
  } finally {
    isRefiningAll.value = false;
  }
};


// ==========================================
// 7. 图片上传与删除
// ==========================================

const triggerUpload = () => {
  if (uploadInputRef.value) {
    uploadInputRef.value.click();
  }
};

const handleFileUpload = async (e) => {
  const files = e.target.files;
  if (!files || files.length === 0) return;
  await uploadFiles(files);
};

const handleFileDrop = async (e) => {
  const files = e.dataTransfer.files;
  if (!files || files.length === 0) return;
  await uploadFiles(files);
};

const uploadFiles = async (files) => {
  const formData = new FormData();
  let imgCount = 0;
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    if (f.type.startsWith('image/')) {
      formData.append('files', f);
      imgCount++;
    }
  }
  
  if (imgCount === 0) return;
  showToast('开始上传图片...', 'info');
  try {
    const res = await fetch(`${API_BASE}/api/labeling/upload?dataset=${currentDataset.value}`, {
      method: 'POST',
      body: formData
    });
    if (res.ok) {
      showToast('图片上传成功！', 'success');
      await fetchImageList();
      await fetchSysInfo();
      if (imageList.value.length > 0 && !currentImage.value) {
        selectImage(imageList.value[0]);
      }
    } else {
      showToast('上传图片失败', 'error');
    }
  } catch (err) {
    console.error('上传图片异常:', err);
    showToast('网络连接异常', 'error');
  }
};

const deleteImage = async (imgName, e) => {
  if (e) e.stopPropagation();
  if (!confirm(`确认删除图片 ${imgName} 吗？\n警告：对应的标签文件也会随之物理删除，不可还原！`)) return;
  
  try {
    const res = await fetch(`${API_BASE}/api/labeling/image/${imgName}?dataset=${currentDataset.value}`, {
      method: 'DELETE'
    });
    
    if (res.ok) {
      showToast('删除成功', 'success');
      await fetchImageList();
      await fetchSysInfo();
      if (currentImage.value && currentImage.value.name === imgName) {
        currentImage.value = null;
        polygons.value = [];
        activePolyIndex.value = null;
      }
    } else {
      showToast('删除失败', 'error');
    }
  } catch (err) {
    console.error('删除图片失败:', err);
    showToast('连接服务端失败', 'error');
  }
};

// ==========================================
// 8. 类别与标注数据保存
// ==========================================

const addClass = async () => {
  const name = prompt('请输入新添加的类别名称：');
  if (name && name.trim()) {
    const trimmed = name.trim();
    if (!classes.value.includes(trimmed)) {
      classes.value.push(trimmed);
      activeClassIndex.value = classes.value.length - 1;
      
      try {
        const res = await fetch(`${API_BASE}/api/labeling/classes?dataset=${currentDataset.value}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ classes: classes.value })
        });
        if (res.ok) {
          showToast(`已成功添加类别标签: ${trimmed}`, 'success');
        }
      } catch (err) {
        console.error('保存类别失败:', err);
        showToast('保存类别失败', 'error');
      }
    } else {
      showToast('类别已存在', 'warning');
    }
  }
};

const getNextImage = () => {
  if (!currentImage.value || filteredImageList.value.length <= 1) return null;
  const idx = filteredImageList.value.findIndex(img => img.name === currentImage.value.name);
  if (idx === -1) return null;
  // 优先选择后面一张，如果没有后面一张，则选择前面一张
  if (idx < filteredImageList.value.length - 1) {
    return filteredImageList.value[idx + 1];
  } else {
    return filteredImageList.value[idx - 1];
  }
};

const saveAnnotations = async () => {
  if (!currentImage.value) return;
  
  // 主动让当前焦点元素失去焦点，防止空格键重复触发
  if (document.activeElement && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }
  
  // 提前计算好下一张图片
  const nextImg = getNextImage();
  
  try {
    const res = await fetch(`${API_BASE}/api/labeling/save?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: currentImage.value.name,
        polygons: polygons.value.map(p => ({
          class_id: p.class_id,
          points: p.points
        }))
      })
    });
    
    if (res.ok) {
      const found = imageList.value.find(img => img.name === currentImage.value.name);
      if (found) {
        found.labeled = polygons.value.length > 0;
        found.label_count = polygons.value.length;
        found.status = polygons.value.length > 0 ? 'labeled' : 'unlabeled';
      }
      showToast('标注数据已保存成功！', 'success');
      
      // 自动跳转到下一张
      if (nextImg) {
        await selectImage(nextImg);
      } else {
        currentImage.value = null;
        polygons.value = [];
        activePolyIndex.value = null;
      }
    } else {
      showToast('保存标注失败', 'error');
    }
  } catch (err) {
    console.error('保存标注出错:', err);
    showToast('保存异常，无法连接服务', 'error');
  }
};


const saveAsNegative = async () => {
  if (!currentImage.value) return;
  
  // 主动让当前焦点元素失去焦点，防止空格键重复触发
  if (document.activeElement && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }
  
  if (polygons.value.length > 0) {
    if (!confirm('警告：此操作将清空当前图片的所有标注多边形。确认继续吗？')) {
      return;
    }
  }
  
  // 提前计算好下一张图片
  const nextImg = getNextImage();
  
  try {
    const res = await fetch(`${API_BASE}/api/labeling/save_negative?dataset=${currentDataset.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: currentImage.value.name
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      showToast('已成功保存为负样本！', 'success');
      
      // 重新拉取图片列表
      await fetchImageList();
      await fetchSysInfo();
      
      // 自动跳转到下一张
      if (nextImg) {
        const foundNext = imageList.value.find(img => img.name === nextImg.name);
        if (foundNext) {
          await selectImage(foundNext);
        } else {
          currentImage.value = null;
          polygons.value = [];
          activePolyIndex.value = null;
        }
      } else {
        currentImage.value = null;
        polygons.value = [];
        activePolyIndex.value = null;
      }
    } else {
      const err = await res.json();
      showToast('保存负样本失败: ' + (err.detail || '接口错误'), 'error');
    }
  } catch (err) {
    console.error('保存负样本出错:', err);
    showToast('保存异常，无法连接服务', 'error');
  }
};

// ==========================================
// 9. 键盘事件监听与生命周期绑定
// ==========================================

const handleKeyDown = (e) => {
  if (currentTab.value !== 'label') return;
  
  // 判断当前焦点是否在输入框内
  const tagName = e.target && e.target.tagName;
  const isInput = tagName === 'INPUT' || tagName === 'TEXTAREA' || (e.target && e.target.isContentEditable);
  
  if (e.key === 'Alt') {
    if (!isInput) {
      e.preventDefault();
      altPressed.value = true;
    }
  }

  if (e.key === '[' || e.key === ']') {
    if (!isInput && (activeTool.value === 'eraser' || (activeTool.value === 'edit' && altPressed.value))) {
      e.preventDefault();
      if (e.key === '[') {
        eraserRadius.value = Math.max(5, eraserRadius.value - 5);
      } else {
        eraserRadius.value = Math.min(100, eraserRadius.value + 5);
      }
    }
  }

  if (e.key === ' ') {
    if (!isInput) {
      e.preventDefault(); // 阻止空格键触发当前焦点按钮的点击事件（标准 HTML 行为中，聚焦按钮按空格会触发 click）
      spacePressed.value = true;
    }
  } else if (e.key === 'Escape') {
    if (activeTool.value === 'draw') {
      activePolygonPoints.value = [];
    } else if (activeTool.value === 'sam') {
      samPrompts.value = [];
      samPreviewPolygon.value = null;
    }
  } else if (e.key === 'Enter') {
    if (activeTool.value === 'draw') {
      finishDrawing();
    } else if (activeTool.value === 'sam') {
      confirmSAM();
    }
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    if (activeTool.value === 'edit' && activePolyIndex.value !== null) {
      deletePolygon(activePolyIndex.value);
    }
  } else if ((e.ctrlKey || e.metaKey || e.altKey) && (e.key === 'r' || e.key === 'R')) {
    if (!isInput && activeTool.value === 'edit' && activePolyIndex.value !== null) {
      e.preventDefault();
      refineSinglePolygon(activePolyIndex.value);
    }
  } else if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z') && !e.shiftKey) {
    // 手动标注模式下未闭合实例逐点撤销（闭合后 activePolygonPoints 已清空，天然不可撤销）
    if (!isInput && activeTool.value === 'draw' && activePolygonPoints.value.length > 0) {
      e.preventDefault();
      undoLastDrawPoint();
    }
  }
};


const handleKeyUp = (e) => {
  if (e.key === ' ') {
    spacePressed.value = false;
  } else if (e.key === 'Alt') {
    altPressed.value = false;
    isErasing.value = false;
    eraserMousePos.value = null;
  }
};

const handleMouseMoveGlobal = (e) => {
  updateMousePos(e);
  if (isErasing.value && eraserMousePos.value) {
    erasePointsAt(eraserMousePos.value[0], eraserMousePos.value[1]);
  }
};

const handleWindowBlur = () => {
  altPressed.value = false;
  isErasing.value = false;
  spacePressed.value = false;
  eraserMousePos.value = null;
};

// 切换 TAB 时刷新数据
watch(currentTab, (newTab) => {
  if (newTab === 'label') {
    fetchImageList();
    fetchClasses();
    fetchModelsList();
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('mousemove', handleMouseMoveGlobal);
    window.addEventListener('blur', handleWindowBlur);
  } else {
    fetchSysInfo();
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('keyup', handleKeyUp);
    window.removeEventListener('mousemove', handleMouseMoveGlobal);
    window.removeEventListener('blur', handleWindowBlur);
  }
});

// 监听训练状态以启停定时器，确保没有训练时只在刷新页面时请求一次
watch(isTraining, (newVal) => {
  if (newVal) {
    if (!statusInterval) {
      statusInterval = setInterval(fetchTrainStatus, 1000);
    }
    if (!sysInfoInterval) {
      sysInfoInterval = setInterval(fetchSysInfo, 3000);
    }
  } else {
    if (statusInterval) {
      clearInterval(statusInterval);
      statusInterval = null;
    }
    if (sysInfoInterval) {
      clearInterval(sysInfoInterval);
      sysInfoInterval = null;
    }
  }
}, { immediate: true });

onMounted(async () => {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light') {
    isDark.value = false;
  } else {
    isDark.value = true;
    if (!savedTheme) {
      localStorage.setItem('theme', 'dark');
    }
  }
  updateThemeClass();

  await fetchDatasets();
  await fetchClasses();

  fetchSysInfo();
  fetchTrainStatus();
  
  window.addEventListener('click', closePromptPopoverOnOutside);
  window.addEventListener('click', closeModelPopoverOnOutside);
  if (currentTab.value === 'label') {
    fetchImageList();
    fetchModelsList();
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('mousemove', handleMouseMoveGlobal);
    window.addEventListener('blur', handleWindowBlur);
  }
});

onUnmounted(() => {
  clearInterval(statusInterval);
  clearInterval(sysInfoInterval);
  closeLogStream();
  
  window.removeEventListener('click', closePromptPopoverOnOutside);
  window.removeEventListener('click', closeModelPopoverOnOutside);
  window.removeEventListener('keydown', handleKeyDown);
  window.removeEventListener('keyup', handleKeyUp);
  window.removeEventListener('mousemove', handleMouseMoveGlobal);
  window.removeEventListener('blur', handleWindowBlur);
});

</script>

<style scoped>
/* 按钮快捷键提示框 */
kbd {
  background: var(--input-bg);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  padding: 1px 4px;
  font-family: 'Outfit', sans-serif;
  font-size: 10px;
}

.svg-eraser-pointer {
  fill: rgba(239, 68, 68, 0.12);
  stroke: #ef4444;
  stroke-width: 1.2px;
  stroke-dasharray: 3 3;
  pointer-events: none; /* 穿透鼠标事件 */
}
</style>
