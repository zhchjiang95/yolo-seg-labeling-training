# YOLO26s-seg 智能分割训练平台

这是一个基于 **FastAPI (后端)** 和 **Vue 3 (前端)** 构建的轻量化 YOLO26s-seg 实例分割训练控制台。专为猪只分割数据集定制，支持自动化数据集解压、随机划分、YOLO 格式 data.yaml 生成、数据增强调整以及控制台日志实时监控。

> 临时放行 9523，如果系统用了 firewalld：
先查看状态：

```bash
sudo firewall-cmd --state
```

放行端口：

```bash
sudo firewall-cmd --permanent --add-port=9523/tcp
sudo firewall-cmd --reload
```
---

## 🌟 核心功能

1. **一键数据集准备**：自动解压并按照指定比例随机划分 `train` / `val` / `test` 数据集。
2. **负样本智能兼容**：支持未标注的负样本，无需手动创建空的 labels 文件，直接把图片放到 images 即可。
3. **训练参数自定义**：配置 epochs、batch size、学习率 (lr0)、早停耐心值 (patience)、输入图片尺寸 (imgsz) 和设备 (device)。
4. **数据增强配置**：直观控制 Mosaic、MixUp、Copy-Paste、旋转及水平/垂直翻转概率。
5. **实时训练监控**：基于 SSE 技术的极客终端，实时流式显示 YOLO 训练控制台输出及当前 Epoch 进度。
6. **硬件负载监测**：实时刷新服务器的 CPU、内存占用以及 GPU 加加速检测状态。
7. **一站式多模式标注**：
   - **手动绘制**：高精度点击打点，支持双击/点击首点闭合多边形。
   - **中点顶点高级编辑**：独创 Midpoint Handles 交互，拖拽相邻边中点即可直接插入顶点微调；双击顶点可快速删除。
   - **一键模型自动识别**：加载已有 YOLO-seg 模型直接预测猪只分割，并调用 RDP 多边形拟合简化算法，减少顶点点数便于人工二次调整。
   - **SAM 智能辅助标注**：左键打绿点（正点），右键打红点（负点），基于 Segment Anything 2.0 模型实时产生高契合度轮廓，按 Enter 直接生成标注。
8. **浅色与深色模式自适应**：系统默认以极简的亮灰色科技风皮肤启动，右上角可一键切换暗色，并在浏览器缓存中记忆选择。

---

## 📂 项目结构

```
xnl-training-platform/
├── datasets/                    # 数据集放置目录
│   ├── labeling/                # 本地数据标注平台图片及标签存放地
│   │   ├── images/              # 用户上传的待标图片目录
│   │   ├── labels/              # 自动保存的归一化 YOLO-seg labels 文件 (.txt)
│   │   └── classes.txt          # 自定义多分类标签清单
│   └── 赶猪通道图集_yolo.zip    # 已标注的数据集压缩包 (未配置本地标注时回退数据源)
├── models/                      # 预训练模型放置目录
│   └── yolo26s-seg.pt           # 预训练权重
│   # 如果要使用 SAM 辅助，建议将权重下载并命名为 models/sam2_b.pt
├── server/                      # FastAPI 后端服务
│   ├── main.py                  # API 路由、标注算法与系统监控
│   ├── trainer.py               # 训练状态机与子进程管道解析
│   ├── dataset_utils.py         # 本地标注优先 / 压缩包解压 8:1:1 自动划分逻辑
│   └── requirements.txt         # 依赖清单
└── web/                         # Vue 3 前端项目
    ├── src/
    │   ├── App.vue              # 融合配置大屏与交互式标注平台的主单页
    │   └── style.css            # 双主题自适应科技感样式系统
    └── package.json
```

---

## 📊 数据集与负样本规则

* **标注数据集优先训练法则**：如果 `datasets/labeling/images` 目录下存在任何已上传图片，系统在点击“一键准备数据集并开始训练”时，将**优先直接划分本地标注目录中的图片和标签**，彻底免去每次解压 zip 压缩包的流程。
* **负样本放置方式**：如果后续有新的负样本图片（即没有任何猪只的背景图），您只需直接将这些图片放入压缩包的 `images` 文件夹，或在标注平台上传图片后不加任何多边形直接保存即可。**不需要**在 `labels` 目录下为它们生成空的 `.txt` 标签文件。
* **分发与训练**：划分数据集时，没有对应标签文件的负样本图片将不会生成 label 目标。YOLO 在训练时找不到对应图片 stem 的标签文件，会自动将其作为背景负样本，以提升模型的抗干扰和降低误检能力。

---

## 🚀 部署与运行指南

本平台支持 **开发联调双服务模式** 以及 **生产单端口一体化托管模式**。

### 方式一：生产环境单端口一体化托管（推荐 🌟）

此方案**不需要**在 GPU 服务器上启动 Node 服务或配置 Nginx，直接使用 FastAPI 后端托管编译后的前端静态文件。

1. **在开发机或服务器上打包前端**：
   ```bash
   cd web
   pnpm install
   pnpm build
   ```
   打包完成后会在 `web/dist` 目录下生成静态文件。
2. **在服务器上启动后端服务**：
   ```bash
   cd server
   pip install -r requirements.txt
   python main.py
   ```
   **效果**：运行 `python main.py` 后，FastAPI 会自动检测并挂载 `web/dist` 目录。您只需在浏览器中直接访问 `http://服务器IP:9523/` 即可同时使用完整的 Web 控制台和后端服务。这种方式从根本上避免了跨域 (CORS) 问题，且部署极为省心。

---

### 方式二：双开发服务联调模式

如果您需要修改前端代码并实时热更新，可选择本模式：

1. **启动后端 API 服务**：
   ```bash
   cd server
   python main.py
   ```
2. **启动前端 Vite 服务**：
   ```bash
   cd web
   pnpm dev
   ```
   启动后，浏览器访问 `http://localhost:5173` 即可。

---

### 方式三：使用 Nginx 代理部署（进阶方案）

如果您的服务器使用 Nginx 统一管理多个站点，可以参考以下配置：

1. **打包前端**：
   在 `web` 目录下运行 `pnpm build`，将生成的 `web/dist` 文件夹拷贝到服务器的 `/var/www/yolo-platform` 目录。
2. **Nginx 配置示例**：
   ```nginx
   server {
       listen 80;
       server_name your_server_ip_or_domain;

       # 前端静态资源托管
       location / {
           root /var/www/yolo-platform;
           index index.html;
           try_files $uri $uri/ /index.html;
       }

       # 后端 API 接口转发
       location /api {
           proxy_pass http://127.0.0.1:9523;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           
           # SSE 流式日志所需的缓冲关闭配置
           proxy_buffering off;
           proxy_cache off;
       }
   }
   ```
3. **启动 Python API 后台进程**（使用 `nohup` 或 `pm2` 等守护进程）：
   ```bash
   cd server
   nohup python main.py > server.log 2>&1 &
   ```

---

## 💻 另一台 GPU 服务器部署说明

由于本平台在开发阶段采用 CPU 运行，部署至 GPU 服务器时需要执行以下配置：

1. **显卡驱动与 PyTorch GPU 安装**：
   确保 GPU 服务器已安装 NVIDIA 驱动，并安装 CUDA 版本的 PyTorch。例如，若显卡支持 CUDA 12.1：
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
   ```
2. **在 Web 中配置训练设备**：
   在 Web 界面左侧的“训练设备”输入框中，将 `cpu` 改为 GPU 的序号：
   * 单显卡配置：`0`
   * 多显卡并行（需 YOLO 分布式训练）：`0,1`
3. **系统自动识别**：
   后端会自动检测 PyTorch 显卡加速状态，若 GPU 加速就绪，系统负载仪表盘中的 "GPU 加速" 将显示为绿色的 "已启用"，并展示对应的显卡型号。

---

## 📝 更新日志

### 2026-06-24
* **优化**：修复“预计剩余时间 (ETA)”估算不准且在某些状态下一直是 `0` 的 Bug。
  * 改进了 `tqdm` 进度条的正则提取逻辑，采用精准前缀匹配，防止与控制台中的其他数值关系（如学习率、Loss `<0.001` 等）产生误匹配导致 ETA 归零。
  * 调整了解析流的控制逻辑，将进度条时间解析前置并剥离 `return`，确保同一行日志中同时存在 Epoch 数据与进度条数据时，ETA 指标不会因前面的匹配提前 `return` 而被跳过。

### 2026-06-26
* **新增**：标注模式模型一键识别悬停下拉列表 (Hover Dropdown) 功能。
  * 支持自动扫描并罗列出系统 `models/` 目录与已训练 `runs/` 目录下的所有 pt 权重模型，方便用户自主选择特定的历史权重或默认权重进行自动识别。
* **重构**：引入高颜值自研 Toast 轻提示系统，全面淘汰了阻塞浏览器主线程的 `alert` 提示，提升交互的丝滑度与顺畅感。
* **适配**：补充并在 `server/requirements.txt` 中写入 `python-multipart`，进一步规避了前端 Form-data 上传依赖丢失的部署隐患；前端项目通过 Vite 重新编译发布并完成了生产包构建。

