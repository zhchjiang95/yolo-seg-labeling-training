<template>
  <Teleport to="body">
    <Transition name="fade-modal">
      <div v-if="modelValue" class="api-modal-backdrop" @click.self="closeModal">
        <div class="api-modal-window">
          <!-- 弹窗头部 -->
          <div class="api-modal-header">
            <div class="api-modal-title-group">
              <div class="api-modal-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <path d="M4 17l6-6-6-6M12 19h8"/>
                </svg>
              </div>
              <div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <h3 class="api-modal-title">第三方系统开放推理接口</h3>
                  <span class="api-tag-badge">v1.0 RESTful</span>
                </div>
                <div class="api-modal-subtitle">
                  支持外部系统直接传图，获取猪只多边形轮廓点、外接矩形框、投影面积与几何质心
                </div>
              </div>
            </div>

            <!-- 头部操作按钮组 -->
            <div class="api-modal-header-actions">
              <button class="api-btn-swagger" @click="openSwagger" title="在 Swagger UI 中进行交互式在线测试">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
                </svg>
                <span>Swagger 在线测试</span>
              </button>
              <button class="api-btn-close" @click="closeModal" title="关闭 (Esc)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 导航 Tabs -->
          <div class="api-modal-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              class="api-tab-btn"
              :class="{ active: activeTab === tab.id }"
              @click="activeTab = tab.id"
            >
              <span class="api-tab-icon">{{ tab.icon }}</span>
              <span>{{ tab.name }}</span>
            </button>
          </div>

          <!-- 内容主体 -->
          <div class="api-modal-body">
            <!-- TAB 1: YOLO 模型分割识别 -->
            <div v-if="activeTab === 'segment'" class="api-tab-content">
              <div class="api-route-card">
                <span class="http-badge post">POST</span>
                <code class="route-path">/api/v1/inference/segment</code>
                <span class="route-format-tag">multipart/form-data (文件直传)</span>
                <button class="copy-small-btn" @click="copyText('/api/v1/inference/segment')">复制路径</button>
              </div>
              <div class="api-route-card" style="margin-top: 8px;">
                <span class="http-badge post">POST</span>
                <code class="route-path">/api/v1/inference/segment/json</code>
                <span class="route-format-tag">application/json (Base64)</span>
                <button class="copy-small-btn" @click="copyText('/api/v1/inference/segment/json')">复制路径</button>
              </div>

              <div class="api-desc-box">
                <strong>接口说明：</strong>无需提前将图片存入平台图库，第三方直接传入图片，调用训练产生的最佳权重（<code>best.pt</code>）或预置 <code>yolo26s-seg.pt</code> 分割模型，毫秒级快速分割识别目标轮廓。
              </div>

              <!-- 参数表 -->
              <h4 class="api-section-title">请求参数说明</h4>
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
                    <td><code>file</code> / <code>image_base64</code></td>
                    <td>File / String</td>
                    <td><span class="required-badge">是</span></td>
                    <td>-</td>
                    <td>图片文件（JPG/PNG/BMP/WebP）或 Base64 编码字符串</td>
                  </tr>
                  <tr>
                    <td><code>conf</code></td>
                    <td>Float</td>
                    <td>否</td>
                    <td><code>0.25</code></td>
                    <td>置信度过滤阈值（0.01 ~ 1.0）</td>
                  </tr>
                  <tr>
                    <td><code>model_path</code></td>
                    <td>String</td>
                    <td>否</td>
                    <td><code>null</code></td>
                    <td>自定义模型权重相对路径（留空则自动选用系统最佳训练权重）</td>
                  </tr>
                  <tr>
                    <td><code>simplify_tolerance</code></td>
                    <td>Float</td>
                    <td>否</td>
                    <td><code>0.003</code></td>
                    <td>多边形轮廓点简化容差系数，设为 0 保留全部原始像素点</td>
                  </tr>
                </tbody>
              </table>

              <!-- 代码示例 -->
              <div class="code-header-bar">
                <span class="code-title">Python 接入示例 (文件直传与 Base64)</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.pythonSegment)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 13px; height: 13px;">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                  复制代码
                </button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.pythonSegment }}</code></pre>
            </div>

            <!-- TAB 2: Prompt 开放词汇识别 -->
            <div v-if="activeTab === 'prompt'" class="api-tab-content">
              <div class="api-route-card">
                <span class="http-badge post">POST</span>
                <code class="route-path">/api/v1/inference/prompt</code>
                <span class="route-format-tag">multipart/form-data</span>
                <button class="copy-small-btn" @click="copyText('/api/v1/inference/prompt')">复制路径</button>
              </div>
              <div class="api-route-card" style="margin-top: 8px;">
                <span class="http-badge post">POST</span>
                <code class="route-path">/api/v1/inference/prompt/json</code>
                <span class="route-format-tag">application/json</span>
                <button class="copy-small-btn" @click="copyText('/api/v1/inference/prompt/json')">复制路径</button>
              </div>

              <div class="api-desc-box">
                <strong>接口说明：</strong>输入任意自然语言提示词（如 <code>"pig"</code>、<code>"pig body, pig ear"</code>），借助 YOLO-World 开放词汇模型或 SAM 3 大模型进行零样本目标定位与高保真多边形轮廓提取。
              </div>

              <!-- 参数表 -->
              <h4 class="api-section-title">请求参数说明</h4>
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
                    <td><code>file</code> / <code>image_base64</code></td>
                    <td>File / String</td>
                    <td><span class="required-badge">是</span></td>
                    <td>-</td>
                    <td>输入图片</td>
                  </tr>
                  <tr>
                    <td><code>prompt</code></td>
                    <td>String</td>
                    <td>否</td>
                    <td><code>"pig"</code></td>
                    <td>文本提示词，支持多个类别用逗号隔开</td>
                  </tr>
                  <tr>
                    <td><code>conf</code></td>
                    <td>Float</td>
                    <td>否</td>
                    <td><code>0.25</code></td>
                    <td>置信度阈值</td>
                  </tr>
                  <tr>
                    <td><code>use_sam</code></td>
                    <td>Boolean</td>
                    <td>否</td>
                    <td><code>true</code></td>
                    <td>是否开启 SAM 提取精细多边形轮廓，为 false 时输出矩形多边形</td>
                  </tr>
                </tbody>
              </table>

              <!-- cURL 示例 -->
              <div class="code-header-bar">
                <span class="code-title">cURL 命令行调用示例</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.curlPrompt)">复制代码</button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.curlPrompt }}</code></pre>
            </div>

            <!-- TAB 3: 可用模型查询 -->
            <div v-if="activeTab === 'models'" class="api-tab-content">
              <div class="api-route-card">
                <span class="http-badge get">GET</span>
                <code class="route-path">/api/v1/inference/models</code>
                <span class="route-format-tag">无需参数</span>
                <button class="copy-small-btn" @click="copyText('/api/v1/inference/models')">复制路径</button>
              </div>
              <div class="api-desc-box">
                <strong>接口说明：</strong>查询当前服务端已就绪的所有分割模型权重（runs 产物与 models/segment）及世界模型权重，返回路径可直接用于上述接口的 <code>model_path</code> 参数。
              </div>

              <div class="code-header-bar">
                <span class="code-title">响应 JSON 格式示例</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.jsonModels)">复制代码</button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.jsonModels }}</code></pre>
            </div>

            <!-- TAB 4: 猪只估重应用与返回数据结构 -->
            <div v-if="activeTab === 'weight'" class="api-tab-content">
              <div class="api-desc-box">
                <strong>💡 猪只体态测算与估重赋能：</strong>
                接口返回的 <code>polygon.points</code>（绝对像素坐标）可直接用于计算猪只体长、体宽与俯视投影面积，为估重模型提供核心输入特征。
              </div>

              <div class="code-header-bar">
                <span class="code-title">核心返回数据结构 (含轮廓点与几何特征)</span>
                <button class="copy-code-btn" @click="copyText(codeExamples.jsonOutput)">复制代码</button>
              </div>
              <pre class="code-block"><code>{{ codeExamples.jsonOutput }}</code></pre>
            </div>
          </div>

          <!-- 弹窗底部 -->
          <div class="api-modal-footer">
            <div class="api-footer-tips">
              <span>💡 提示：服务默认端口为 <code>9523</code>，外部系统调用需确保防火墙开放对应端口。</span>
            </div>
            <button class="api-btn-primary" @click="closeModal">我知道了</button>
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

const activeTab = ref('segment');

const tabs = [
  { id: 'segment', name: 'YOLO 专用分割识别', icon: '⚡' },
  { id: 'prompt', name: 'Prompt 开放词汇识别', icon: '💬' },
  { id: 'models', name: '可用模型列表查询', icon: '📦' },
  { id: 'weight', name: '返回结构与估重赋能', icon: '📐' }
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

// 打开 Swagger UI
const openSwagger = () => {
  const host = window.location.hostname || '127.0.0.1';
  window.open(`http://${host}:9523/docs`, '_blank');
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

// 代码示例字典
const codeExamples = {
  pythonSegment: `# 1. 文件直接上传调用
import requests

url = "http://<server-ip>:9523/api/v1/inference/segment"
with open("pig.jpg", "rb") as f:
    files = {"file": ("pig.jpg", f, "image/jpeg")}
    data = {"conf": 0.25, "simplify_tolerance": 0.003}
    res = requests.post(url, files=files, data=data).json()

if res["code"] == 200:
    for target in res["data"]["predictions"]:
        print(f"目标类别: {target['class_name']}, 置信度: {target['confidence']}")
        print(f"轮廓点数: {target['polygon']['point_count']}")
        print(f"绝对坐标: {target['polygon']['points']}")
        print(f"像素投影面积: {target['polygon']['area_pixels']} px^2")

# 2. Base64 编码方式调用
import base64
with open("pig.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")

payload = {"image_base64": b64, "conf": 0.25}
res_json = requests.post("http://<server-ip>:9523/api/v1/inference/segment/json", json=payload).json()`,

  curlPrompt: `# 上传图片并输入 Prompt 识别猪只轮廓
curl -X POST "http://<server-ip>:9523/api/v1/inference/prompt" \\
     -F "file=@/path/to/pig.jpg" \\
     -F "prompt=pig" \\
     -F "conf=0.25" \\
     -F "use_sam=true"`,

  jsonModels: `{
  "code": 200,
  "message": "success",
  "data": {
    "segment_models": [
      {
        "name": "best.pt (最佳训练权重)",
        "path": "runs/segment/yolo26s_train/weights/best.pt",
        "type": "trained",
        "is_best": true
      },
      {
        "name": "yolo26s-seg.pt",
        "path": "models/segment/yolo26s-seg.pt",
        "type": "pretrained",
        "is_default": true
      }
    ],
    "world_models": [
      {
        "name": "yolov8l-worldv2.pt",
        "path": "models/world/yolov8l-worldv2.pt",
        "type": "world_model"
      }
    ]
  }
}`,

  jsonOutput: `{
  "code": 200,
  "message": "success",
  "data": {
    "image_info": { "width": 1280, "height": 720, "channels": 3 },
    "count": 1,
    "predictions": [
      {
        "id": 1,
        "class_id": 0,
        "class_name": "pig",
        "confidence": 0.9426,
        "box": {
          "xyxy": [180.5, 95.2, 940.3, 610.8],
          "xyxy_normalized": [0.141, 0.132, 0.735, 0.848]
        },
        "polygon": {
          "points": [[250.0, 100.5], [890.1, 230.6], [720.5, 610.8], [210.0, 520.4]],
          "points_normalized": [[0.195, 0.139], [0.695, 0.320], [0.563, 0.848], [0.164, 0.723]],
          "point_count": 4,
          "area_pixels": 268420.5,
          "centroid": [530.2, 385.6]
        }
      }
    ],
    "latency_ms": 35.8
  }
}`
};
</script>

<style scoped>
.api-modal-backdrop {
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

.api-modal-window {
  width: 900px;
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

.api-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  background: rgba(255, 255, 255, 0.02);
}

.api-modal-title-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.api-modal-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(147, 51, 234, 0.2));
  border: 1px solid rgba(59, 130, 246, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #60a5fa;
}

.api-modal-icon svg {
  width: 20px;
  height: 20px;
}

.api-modal-title {
  font-size: 17px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}

.api-tag-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 9999px;
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
  font-weight: 600;
}

.api-modal-subtitle {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  margin-top: 3px;
}

.api-modal-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.api-btn-swagger {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
  padding: 7px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.api-btn-swagger:hover {
  background: rgba(59, 130, 246, 0.25);
  border-color: #60a5fa;
  transform: translateY(-1px);
}

.api-btn-swagger svg {
  width: 14px;
  height: 14px;
}

.api-btn-close {
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

.api-btn-close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.api-btn-close svg {
  width: 18px;
  height: 18px;
}

.api-modal-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: rgba(0, 0, 0, 0.15);
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  overflow-x: auto;
}

.api-tab-btn {
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

.api-tab-btn:hover {
  color: var(--text, #f1f5f9);
  background: rgba(255, 255, 255, 0.04);
}

.api-tab-btn.active {
  color: #fff;
  background: rgba(59, 130, 246, 0.18);
  border-color: rgba(59, 130, 246, 0.35);
  font-weight: 600;
}

.api-modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.api-route-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(0, 0, 0, 0.25);
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
}

.http-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: 0.03em;
}

.http-badge.post {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.35);
}

.http-badge.get {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.35);
}

.route-path {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 14px;
  font-weight: 600;
  color: #38bdf8;
}

.route-format-tag {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
  margin-left: auto;
}

.copy-small-btn {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text, #e2e8f0);
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.copy-small-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}

.api-desc-box {
  margin-top: 14px;
  padding: 12px 16px;
  background: rgba(59, 130, 246, 0.07);
  border-left: 3px solid #3b82f6;
  border-radius: 4px 8px 8px 4px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text, #cbd5e1);
}

.api-section-title {
  font-size: 14px;
  font-weight: 700;
  margin: 18px 0 10px 0;
  letter-spacing: -0.01em;
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

.required-badge {
  color: #f87171;
  font-weight: 700;
}

.code-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 18px;
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

.api-modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  border-top: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  background: rgba(255, 255, 255, 0.02);
}

.api-footer-tips {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

.api-btn-primary {
  background: #3b82f6;
  color: #fff;
  border: none;
  padding: 7px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.api-btn-primary:hover {
  background: #2563eb;
}

/* 遮罩过渡动画 */
.fade-modal-enter-active,
.fade-modal-leave-active {
  transition: opacity 0.22s ease;
}

.fade-modal-enter-from,
.fade-modal-leave-to {
  opacity: 0;
}
</style>
