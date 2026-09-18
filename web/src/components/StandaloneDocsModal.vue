<template>
  <Teleport to="body">
    <Transition name="fade-modal">
      <div v-if="modelValue" class="standalone-modal-backdrop" @click.self="closeModal">
        <div class="standalone-modal-window">
          <!-- 弹窗头部 -->
          <div class="standalone-modal-header">
            <div class="standalone-modal-title-group">
              <div class="standalone-modal-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                  <line x1="8" y1="21" x2="16" y2="21"/>
                  <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
              </div>
              <div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <h3 class="standalone-modal-title">共享独立标注微工作台集成指南</h3>
                  <span class="standalone-tag-badge">iframe 嵌入 & 弹窗双模式</span>
                </div>
                <div class="standalone-modal-subtitle">
                  外部业务系统（如质检后台、ERP、资产库）无需搬迁数据，直接内嵌本平台全功能标注与 SAM 智能分割
                </div>
              </div>
            </div>

            <!-- 头部操作按钮组 -->
            <div class="standalone-modal-header-actions">
              <button class="standalone-btn-demo" @click="openDemoWindow" title="新窗口打开独立工作台体验效果">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
                </svg>
                <span>立即体验演示</span>
              </button>
              <button class="standalone-btn-close" @click="closeModal" title="关闭 (Esc)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 导航 Tabs -->
          <div class="standalone-modal-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              class="standalone-tab-btn"
              :class="{ active: activeTab === tab.id }"
              @click="activeTab = tab.id"
            >
              <span class="tab-icon">{{ tab.icon }}</span>
              <span>{{ tab.name }}</span>
            </button>
          </div>

          <!-- 内容主体 -->
          <div class="standalone-modal-body">
            <!-- TAB 1: iframe 嵌入对接 -->
            <div v-if="activeTab === 'iframe'" class="tab-content-panel">
              <div class="feature-tip-box">
                <strong>💡 iframe 嵌入模式优势：</strong>
                可以将标注界面作为子组件直接嵌入到第三方系统的页面、抽屉（Drawer）或模态弹窗（Modal）中。
                操作员在第三方后台内即可完成无感打标，标注完成后通过 <code>window.parent.postMessage</code> 自动回传数据并关闭或刷新视图。
              </div>

              <h4 class="section-title">1. Vue 3 极简嵌入封装示例</h4>
              <div class="code-header-bar">
                <span class="code-title">AnnotatorIframe.vue</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.vueIframe)">复制代码</button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.vueIframe }}</code></pre>

              <h4 class="section-title" style="margin-top: 20px;">2. 原生 HTML / JavaScript 嵌入方式</h4>
              <div class="code-header-bar">
                <span class="code-title">index.html</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.htmlIframe)">复制代码</button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.htmlIframe }}</code></pre>
            </div>

            <!-- TAB 2: window.open 弹窗对接 -->
            <div v-if="activeTab === 'window'" class="tab-content-panel">
              <div class="feature-tip-box">
                <strong>💡 window.open 弹窗模式优势：</strong>
                在新浏览器标签页中全屏运行，拥有最大的操作视野。标注完成后自动向主窗口 (<code>window.opener</code>) 回传结果并自动执行 <code>window.close()</code>。
              </div>

              <div class="code-header-bar">
                <span class="code-title">原生 JavaScript 弹出窗口调用</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.windowOpen)">复制代码</button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.windowOpen }}</code></pre>
            </div>

            <!-- TAB 3: 通信协议与参数规范 -->
            <div v-if="activeTab === 'protocol'" class="tab-content-panel">
              <h4 class="section-title">URL 启动参数说明</h4>
              <table class="api-table">
                <thead>
                  <tr>
                    <th>参数名</th>
                    <th>类型</th>
                    <th>必填</th>
                    <th>默认值</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><code>mode</code></td>
                    <td>String</td>
                    <td><span class="badge-req">是</span></td>
                    <td>-</td>
                    <td>固定传 <code>standalone</code>，进入无状态独立标注模式</td>
                  </tr>
                  <tr>
                    <td><code>key</code></td>
                    <td>String</td>
                    <td><span class="badge-req">是</span></td>
                    <td>-</td>
                    <td>图片在调用方系统的唯一标识（如文件名、工单号、UUID）</td>
                  </tr>
                  <tr>
                    <td><code>image</code></td>
                    <td>String</td>
                    <td>否</td>
                    <td>-</td>
                    <td>待标注图片的网络可访问 URL（建议 <code>encodeURIComponent</code> 转义）</td>
                  </tr>
                  <tr>
                    <td><code>classes</code></td>
                    <td>String</td>
                    <td>否</td>
                    <td><code>目标</code></td>
                    <td>自定义分类标签，英文逗号分隔（如 <code>猪只,耳朵,尾巴</code>）</td>
                  </tr>
                  <tr>
                    <td><code>annotations</code></td>
                    <td>String</td>
                    <td>否</td>
                    <td><code>[]</code></td>
                    <td>历史标注多边形数据（JSON 格式字符串），用于二次修改或审核回显</td>
                  </tr>
                  <tr>
                    <td><code>autoClose</code></td>
                    <td>Boolean</td>
                    <td>否</td>
                    <td><code>true</code></td>
                    <td>完成回传后是否自动执行关闭（在 window.open 下有效）</td>
                  </tr>
                </tbody>
              </table>

              <h4 class="section-title" style="margin-top: 24px;">回传消息数据结构 (ANNOTATOR_SAVE)</h4>
              <div class="code-header-bar">
                <span class="code-title">postMessage 数据 Payload</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.jsonSave)">复制代码</button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.jsonSave }}</code></pre>
            </div>

            <!-- TAB 4: 大数据握手与性能特性 -->
            <div v-if="activeTab === 'features'" class="tab-content-panel">
              <div class="feature-card-grid">
                <div class="feature-card">
                  <div class="card-icon">⚡</div>
                  <div class="card-title">零跨域同源限制 (Zero CORS)</div>
                  <div class="card-desc">双方页面仅需在浏览器内存中通过 postMessage 事件通信，彻底绕过浏览器的同源策略，第三方无需配置任何复杂反向代理。</div>
                </div>
                <div class="feature-card">
                  <div class="card-icon">🤖</div>
                  <div class="card-title">全量 AI 算力无缝接入</div>
                  <div class="card-desc">外部图片自动载入 _temp 沙箱，支持 SAM 交互打点、SAM Refine 边缘重分割、YOLO 自动检测等全套模型能力，退出即刻自动销毁清理。</div>
                </div>
                <div class="feature-card">
                  <div class="card-icon">🤝</div>
                  <div class="card-title">双向主动握手 (INIT_DATA)</div>
                  <div class="card-desc">突破浏览器 URL 参数 2KB 长度限制。调用方页面在监听到 <code>ANNOTATOR_READY</code> 后，可向子窗口主动投递超大 Base64 图片或成百上千个历史多边形。</div>
                </div>
                <div class="feature-card">
                  <div class="card-icon">🎯</div>
                  <div class="card-title">标准归一化坐标输出</div>
                  <div class="card-desc">回传的多边形点集 points 均为 0.0 ~ 1.0 的归一化比例坐标，天然契合 YOLO Segmentation 训练格式与任意分辨率显示屏。</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 弹窗底部 -->
          <div class="standalone-modal-footer">
            <div class="footer-tips">
              <span>💡 提示：在 iframe 嵌入时，建议设置容器高度不低于 <code>600px</code> 以获得舒适的画布打点体验。</span>
            </div>
            <button class="btn-confirm" @click="closeModal">我知道了</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue']);

const activeTab = ref('iframe');

const tabs = [
  { id: 'iframe', name: 'iframe 嵌入对接', icon: '🖼️' },
  { id: 'window', name: 'window.open 弹窗对接', icon: '🪟' },
  { id: 'protocol', name: '通信协议与参数', icon: '📋' },
  { id: 'features', name: '双向握手与算力优势', icon: '⚡' }
];

const closeModal = () => {
  emit('update:modelValue', false);
};

// 监听 Esc 键关闭
const handleKeyDown = (e) => {
  if (e.key === 'Escape' && props.modelValue) {
    closeModal();
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});

// 打开体验演示窗口
const openDemoWindow = () => {
  const host = window.location.origin || 'http://localhost:5173';
  const demoUrl = `${host}/?mode=standalone&key=demo_sample_001.jpg&classes=${encodeURIComponent('猪只,耳朵,尾巴')}`;
  window.open(demoUrl, '_blank');
};

// 复制文本提示
const copyText = (text) => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      alert('已成功复制到剪贴板！');
    }).catch(() => {
      prompt('请手动复制：', text);
    });
  } else {
    prompt('请手动复制：', text);
  }
};

// 示例代码字典
const codeExamples = {
  vueIframe: `<template>
  <div class="annotator-container">
    <!-- 嵌入标注工作台 -->
    <iframe
      ref="annotatorFrame"
      :src="annotatorUrl"
      class="annotator-iframe"
      allow="clipboard-write"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  imageKey: { type: String, required: true },
  imageUrl: { type: String, required: true },
  classes: { type: Array, default: () => ['猪只', '耳朵', '背部'] }
});

const emit = defineEmits(['save', 'cancel']);

// 拼接独立工作台启动地址 (指向标注平台地址)
const PLATFORM_HOST = 'http://<server-ip>:9523';
const annotatorUrl = computed(() => {
  const params = new URLSearchParams({
    mode: 'standalone',
    key: props.imageKey,
    image: props.imageUrl,
    classes: props.classes.join(',')
  });
  return \`\${PLATFORM_HOST}/?\${params.toString()}\`;
});

// 监听 iframe postMessage 回传事件
const onMessage = (event) => {
  const data = event.data;
  if (!data || typeof data !== 'object') return;

  // 1. 用户点击【完成并回传】或按下 Ctrl+S
  if (data.type === 'ANNOTATOR_SAVE' && data.key === props.imageKey) {
    console.log('✅ 收到多边形标注结果:', data.polygons);
    emit('save', data);
  }

  // 2. 用户点击【取消】
  if (data.type === 'ANNOTATOR_CANCEL' && data.key === props.imageKey) {
    console.log('操作员取消了标注');
    emit('cancel');
  }
};

onMounted(() => {
  window.addEventListener('message', onMessage);
});

onUnmounted(() => {
  window.removeEventListener('message', onMessage);
});
<\/script>

<style scoped>
.annotator-container {
  width: 100%;
  height: 800px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.annotator-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>`,

  htmlIframe: `<!-- HTML 页面直接嵌入 iframe -->
<div style="width: 1000px; height: 650px; border: 1px solid #ccc; border-radius: 8px; overflow: hidden;">
  <iframe
    id="myAnnotatorFrame"
    src="http://<server-ip>:9523/?mode=standalone&key=pig_001.jpg&image=https://example.com/pig.jpg&classes=猪只,头部"
    style="width: 100%; height: 100%; border: none;"
  ></iframe>
</div>

<script>
window.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || typeof data !== 'object') return;

  if (data.type === 'ANNOTATOR_SAVE') {
    console.log('成功获取标注数据：', data.polygons);
    // 调用业务后台保存接口
    saveToMyDatabase(data);
  }

  if (data.type === 'ANNOTATOR_CANCEL') {
    console.log('操作员点击了取消');
  }
});
<\/script>`,

  windowOpen: `// 第三方后台点击按钮弹出标注窗口
const openAnnotator = () => {
  const key = 'pig_sample_101.jpg';
  const imgUrl = 'https://example.com/pig.jpg';
  const classes = '猪只,耳朵,尾巴';

  const targetUrl = \`http://<server-ip>:9523/?mode=standalone&key=\${encodeURIComponent(key)}&image=\${encodeURIComponent(imgUrl)}&classes=\${encodeURIComponent(classes)}\`;
  const popup = window.open(targetUrl, '_blank');

  // 监听回传消息
  const handleMessage = (event) => {
    const data = event.data;
    if (!data || typeof data !== 'object') return;

    if (data.type === 'ANNOTATOR_SAVE' && data.key === key) {
      console.log('标注完成，结果:', data.polygons);
      window.removeEventListener('message', handleMessage);
    }
    if (data.type === 'ANNOTATOR_CANCEL' && data.key === key) {
      console.log('用户取消标注');
      window.removeEventListener('message', handleMessage);
    }
  };

  window.addEventListener('message', handleMessage);
};`,

  jsonSave: `{
  "type": "ANNOTATOR_SAVE",
  "key": "pig_sample_101.jpg",
  "timestamp": 1726661234567,
  "is_negative": false,
  "image": {
    "name": "pig_sample_101_temp.jpg",
    "width": 1920,
    "height": 1080
  },
  "classes": ["猪只", "耳朵", "尾巴"],
  "polygons": [
    {
      "class_id": 0,
      "class_name": "猪只",
      "points": [
        [0.125, 0.231],
        [0.210, 0.245],
        [0.450, 0.612],
        [0.198, 0.580]
      ]
    }
  ]
}`
};
</script>

<style scoped>
.standalone-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 15, 29, 0.75);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
  padding: 24px;
}

.standalone-modal-window {
  width: 920px;
  max-width: 95vw;
  max-height: 88vh;
  background: var(--surface, #1e293b);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.12));
  border-radius: 18px;
  box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--text, #f8fafc);
  animation: modalScaleIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modalScaleIn {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.standalone-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  background: rgba(255, 255, 255, 0.02);
}

.standalone-modal-title-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.standalone-modal-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(59, 130, 246, 0.2));
  border: 1px solid rgba(16, 185, 129, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #34d399;
}

.standalone-modal-icon svg {
  width: 22px;
  height: 22px;
}

.standalone-modal-title {
  font-size: 17px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}

.standalone-tag-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 9999px;
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
  font-weight: 600;
}

.standalone-modal-subtitle {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  margin-top: 3px;
}

.standalone-modal-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.standalone-btn-demo {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
  padding: 7px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.standalone-btn-demo:hover {
  background: rgba(16, 185, 129, 0.25);
  border-color: #34d399;
  transform: translateY(-1px);
}

.standalone-btn-demo svg {
  width: 14px;
  height: 14px;
}

.standalone-btn-close {
  background: transparent;
  border: none;
  color: var(--text-muted, #94a3b8);
  cursor: pointer;
  padding: 6px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.standalone-btn-close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.standalone-btn-close svg {
  width: 18px;
  height: 18px;
}

.standalone-modal-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: rgba(0, 0, 0, 0.15);
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  overflow-x: auto;
}

.standalone-tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted, #94a3b8);
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.18s;
  white-space: nowrap;
}

.standalone-tab-btn:hover {
  color: var(--text, #f1f5f9);
  background: rgba(255, 255, 255, 0.04);
}

.standalone-tab-btn.active {
  color: #fff;
  background: rgba(16, 185, 129, 0.18);
  border-color: rgba(16, 185, 129, 0.35);
  font-weight: 600;
}

.standalone-modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.feature-tip-box {
  padding: 12px 16px;
  background: rgba(16, 185, 129, 0.08);
  border-left: 3px solid #10b981;
  border-radius: 4px 8px 8px 4px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text, #cbd5e1);
  margin-bottom: 18px;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  margin: 16px 0 8px 0;
  color: var(--text, #f1f5f9);
}

.api-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  text-align: left;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
}

.api-table th {
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  font-weight: 600;
  color: var(--text-muted, #94a3b8);
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.06));
}

.api-table td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.04));
  color: var(--text, #cbd5e1);
}

.badge-req {
  color: #f87171;
  font-weight: 700;
}

.code-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  padding: 6px 12px;
  background: rgba(15, 23, 42, 0.7);
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-bottom: none;
}

.code-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted, #94a3b8);
}

.copy-code-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  color: #38bdf8;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  padding: 3px 8px;
  border-radius: 4px;
  transition: all 0.15s;
}

.copy-code-btn:hover {
  background: rgba(56, 189, 248, 0.15);
}

.code-block {
  margin: 0;
  padding: 14px;
  background: #0f172a;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  color: #e2e8f0;
  overflow-x: auto;
  white-space: pre;
}

.feature-card-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-top: 8px;
}

.feature-card {
  padding: 16px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.07));
  border-radius: 12px;
  transition: transform 0.2s;
}

.feature-card:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.3);
}

.card-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text, #f1f5f9);
  margin-bottom: 6px;
}

.card-desc {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  line-height: 1.6;
}

.standalone-modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  border-top: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  background: rgba(255, 255, 255, 0.02);
}

.footer-tips {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

.btn-confirm {
  background: #10b981;
  color: #fff;
  border: none;
  padding: 7px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-confirm:hover {
  background: #059669;
}

/* 过渡动画 */
.fade-modal-enter-active,
.fade-modal-leave-active {
  transition: opacity 0.22s ease;
}

.fade-modal-enter-from,
.fade-modal-leave-to {
  opacity: 0;
}
</style>
