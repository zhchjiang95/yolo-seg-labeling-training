# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import psutil
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 将当前目录加入 Python Path 以确保模块导入
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trainer import YOLOTrainer

# 确定工作空间根目录
WORKSPACE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent.resolve()

app = FastAPI(title="YOLO26s-seg 训练控制台后端 API")

# 配置 CORS 允许跨域（前端 Vite 默认端口 5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源访问，便于局域网/多服务器部署调试
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保 labeling 目录结构存在
labeling_dir = WORKSPACE_DIR / "datasets" / "labeling"
labeling_images_dir = labeling_dir / "images"
labeling_labels_dir = labeling_dir / "labels"
labeling_images_dir.mkdir(parents=True, exist_ok=True)
labeling_labels_dir.mkdir(parents=True, exist_ok=True)

# 创建默认的 classes.txt
classes_file = labeling_dir / "classes.txt"
if not classes_file.exists():
    with open(classes_file, "w", encoding="utf-8") as f:
        f.write("pig\n")

# 挂载标注图片静态资源（使得前端可以直接渲染本地图片）
app.mount("/labeling_images", StaticFiles(directory=str(labeling_images_dir)), name="labeling_images")

# 初始化训练管理器
trainer = YOLOTrainer(str(WORKSPACE_DIR))

# 请求体结构校验模型
class TrainStartRequest(BaseModel):
    epochs: int = Field(default=300, ge=1, le=10000, description="训练轮次")
    batch: int = Field(default=4, ge=1, le=256, description="批次大小")
    lr0: float = Field(default=0.001, gt=0.0, le=1.0, description="初始学习率")
    patience: int = Field(default=50, ge=0, description="早停耐心值")
    imgsz: int = Field(default=960, ge=32, le=2048, description="输入图像尺寸")
    device: str = Field(default="0", description="训练设备：cpu, 0, 1, 0,1 等")
    split_ratio: str = Field(default="8:1:1", description="数据集划分比例 (train:val:test)")
    # 数据增强配置
    mosaic: float = Field(default=0.5, ge=0.0, le=1.0, description="Mosaic 比例")
    mixup: float = Field(default=0.0, ge=0.0, le=1.0, description="MixUp 比例")
    copy_paste: float = Field(default=0.3, ge=0.0, le=1.0, description="Copy-Paste 比例")
    fliplr: float = Field(default=0.5, ge=0.0, le=1.0, description="左右翻转概率")
    flipud: float = Field(default=0.5, ge=0.0, le=1.0, description="上下翻转概率")
    degrees: float = Field(default=180.0, ge=0.0, le=180.0, description="随机旋转角度")

@app.post("/api/start")
def start_train(req: TrainStartRequest):
    """启动训练任务"""
    config = req.model_dump()
    success = trainer.start_training(config)
    if not success:
        raise HTTPException(status_code=400, detail="训练任务已在运行中，无法重复启动")
    return {"status": "success", "message": "训练任务已成功启动"}

@app.post("/api/stop")
def stop_train():
    """中止训练任务"""
    success = trainer.stop_training()
    if not success:
        raise HTTPException(status_code=400, detail="当前没有正在运行的训练任务")
    return {"status": "success", "message": "训练任务已中止"}

@app.get("/api/status")
def get_status():
    """获取训练状态和进度数据"""
    return trainer.get_status()

@app.get("/api/sysinfo")
def get_sysinfo():
    """获取服务器系统硬件和数据集概要信息"""
    # 1. 硬件信息
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    
    gpu_available = False
    gpu_name = "N/A"
    gpu_memory_used = 0
    gpu_memory_total = 0
    
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory_used = torch.cuda.memory_allocated(0) / (1024 ** 2)  # MB
    except Exception:
        pass

    # 2. 数据集状态判定 (zip 或者是本地标注目录)
    zip_file = WORKSPACE_DIR / "datasets" / "赶猪通道图集_yolo.zip"
    local_img_dir = WORKSPACE_DIR / "datasets" / "labeling" / "images"
    
    dataset_status = "missing"
    dataset_size_mb = 0.0
    dataset_path_str = "无"
    
    # 检查本地标注图片数
    local_images_count = 0
    if local_img_dir.exists():
        local_images_count = len([f for f in local_img_dir.iterdir() if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}])

    if zip_file.exists():
        dataset_status = "ready"
        dataset_size_mb = round(zip_file.stat().st_size / (1024 ** 2), 2)
        dataset_path_str = zip_file.name
    elif local_images_count > 0:
        dataset_status = "ready"
        dataset_size_mb = 0.0
        dataset_path_str = f"本地标注数据集 ({local_images_count}张图片)"

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024 ** 3), 2),
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
        "dataset_status": dataset_status,
        "dataset_size_mb": dataset_size_mb,
        "dataset_path": dataset_path_str
    }

# ==========================================
# 标注模块接口及模型预测器
# ==========================================

class PolygonItem(BaseModel):
    class_id: int
    points: List[List[float]] = Field(..., description="归一化多边形顶点，如 [[x1, y1], [x2, y2], ...]")

class SaveAnnotationRequest(BaseModel):
    name: str
    polygons: List[PolygonItem]

class SAMPredictRequest(BaseModel):
    name: str
    points: List[List[float]] = Field(..., description="点击坐标 [[x1, y1], ...]")
    labels: List[int] = Field(..., description="点击类型 [1, 0, ...]")

class ClassesUpdateRequest(BaseModel):
    classes: List[str]

def simplify_polygon(points_list: List[List[float]], tolerance: float = 0.003) -> List[List[float]]:
    """
    使用 OpenCV 的 RDP 算法对多边形点进行简化，减少顶点数以利于前端编辑。
    """
    if len(points_list) < 4:
        return points_list
    pts = np.array(points_list, dtype=np.float32)
    perimeter = cv2.arcLength(pts, True)
    epsilon = tolerance * perimeter
    approx = cv2.approxPolyDP(pts, epsilon, True)
    simplified = approx.reshape(-1, 2).tolist()
    if len(simplified) >= 3:
        return simplified
    return points_list

class LabelingPredictor:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.yolo_models = {}  # 缓存已加载的 YOLO 实例: path_str -> model
        self.sam_model = None

    def get_yolo_model(self, custom_path: str = None):
        # 1. 如果传入了特定模型路径
        if custom_path:
            path_obj = Path(custom_path)
            if not path_obj.is_absolute():
                full_path = self.workspace_dir / path_obj
            else:
                full_path = path_obj
            
            full_path_str = str(full_path.resolve())
            if full_path_str not in self.yolo_models:
                if not full_path.exists():
                    raise FileNotFoundError(f"指定的模型权重不存在: {full_path.name}")
                from ultralytics import YOLO
                self.yolo_models[full_path_str] = YOLO(full_path_str)
            return self.yolo_models[full_path_str]

        # 2. 默认模型加载逻辑
        best_pt = self.workspace_dir / "runs" / "segment" / "yolo26s_train" / "weights" / "best.pt"
        if best_pt.exists():
            default_path = best_pt
        else:
            default_path = self.workspace_dir / "models" / "yolo26s-seg.pt"
        
        default_path_str = str(default_path.resolve())
        if default_path_str not in self.yolo_models:
            if not default_path.exists():
                raise FileNotFoundError(f"默认模型权重不存在: {default_path.name}")
            from ultralytics import YOLO
            self.yolo_models[default_path_str] = YOLO(default_path_str)
        return self.yolo_models[default_path_str]

    def get_sam_model(self):
        if self.sam_model is None:
            sam_names = [
                "sam3.1_multiplex.pt", 
                "sam3.1.pt", 
                "sam3.pt", 
                "sam2_b.pt", 
                "sam_b.pt", 
                "mobile_sam.pt", 
                "sam2_t.pt"
            ]
            found_path = None
            for name in sam_names:
                p = self.workspace_dir / "models" / name
                if p.exists():
                    found_path = p
                    break
            if found_path is None:
                raise FileNotFoundError("未在 models/ 目录下检测到 SAM 权重 (例如 sam3.1_multiplex.pt、sam3.pt、sam2_b.pt、mobile_sam.pt)。")
            
            from ultralytics import SAM
            self.sam_model = SAM(str(found_path))
        return self.sam_model

predictor = LabelingPredictor(WORKSPACE_DIR)

# 1. 获取图片列表
@app.get("/api/labeling/images")
def get_labeling_images():
    image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    images_dir = WORKSPACE_DIR / "datasets" / "labeling" / "images"
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / "labels"
    
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    
    result = []
    for item in images_dir.iterdir():
        if item.is_file() and item.suffix.lower() in image_exts:
            # 检查是否有对应 label 文件
            label_name = item.stem + ".txt"
            label_path = labels_dir / label_name
            labeled = False
            label_count = 0
            if label_path.exists() and label_path.stat().st_size > 0:
                try:
                    with open(label_path, "r", encoding="utf-8") as f:
                        lines = [line.strip() for line in f if line.strip()]
                        label_count = len(lines)
                        labeled = label_count > 0
                except Exception as e:
                    print(f"读取 label 文件行数出错 {label_path}: {e}")
            
            result.append({
                "name": item.name,
                "labeled": labeled,
                "label_count": label_count,
                "size_kb": round(item.stat().st_size / 1024, 1),
                "mtime": int(item.stat().st_mtime)
            })
    # 按最后修改时间倒序排列
    result.sort(key=lambda x: x["mtime"], reverse=True)
    return result

# 2. 上传图片
@app.post("/api/labeling/upload")
async def upload_labeling_images(files: List[UploadFile] = File(...)):
    images_dir = WORKSPACE_DIR / "datasets" / "labeling" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    saved_files = []
    for file in files:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
            continue
        
        target_path = images_dir / file.filename
        content = await file.read()
        with open(target_path, "wb") as f:
            f.write(content)
        saved_files.append(file.filename)
        
    return {"status": "success", "uploaded": saved_files}

# 3. 删除图片
@app.delete("/api/labeling/image/{name}")
def delete_labeling_image(name: str):
    images_dir = WORKSPACE_DIR / "datasets" / "labeling" / "images"
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / "labels"
    
    img_path = images_dir / name
    if img_path.exists():
        img_path.unlink()
        
    label_path = labels_dir / (Path(name).stem + ".txt")
    if label_path.exists():
        label_path.unlink()
        
    return {"status": "success", "message": f"图片 {name} 及其标签已被删除"}

# 4. 获取已有标注和 classes 列表
@app.get("/api/labeling/labels/{name}")
def get_labeling_labels(name: str):
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / "labels"
    classes_file = WORKSPACE_DIR / "datasets" / "labeling" / "classes.txt"
    
    classes = ["pig"]
    if classes_file.exists():
        with open(classes_file, "r", encoding="utf-8", errors="ignore") as f:
            classes = [line.strip() for line in f if line.strip()]
            
    label_path = labels_dir / (Path(name).stem + ".txt")
    polygons = []
    
    if label_path.exists():
        with open(label_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 7:  # class_id 加上至少3个点
                    try:
                        class_id = int(parts[0])
                        coords = [float(x) for x in parts[1:]]
                        points = []
                        for i in range(0, len(coords), 2):
                            if i + 1 < len(coords):
                                points.append([coords[i], coords[i+1]])
                        # 简化多边形点数
                        points = simplify_polygon(points)
                        polygons.append({
                            "class_id": class_id,
                            "points": points
                        })
                    except Exception:
                        pass
                        
    return {
        "classes": classes,
        "polygons": polygons
    }

# 5. 保存标注
@app.post("/api/labeling/save")
def save_labeling_labels(req: SaveAnnotationRequest):
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    
    label_path = labels_dir / (Path(req.name).stem + ".txt")
    
    lines = []
    for poly in req.polygons:
        if len(poly.points) < 3:
            continue
        coords_str = " ".join([f"{p[0]:.6f} {p[1]:.6f}" for p in poly.points])
        lines.append(f"{poly.class_id} {coords_str}\n")
        
    with open(label_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    return {"status": "success", "message": f"{req.name} 标注已保存"}

# 6. 获取和更新 Classes
@app.post("/api/labeling/classes")
def update_labeling_classes(req: ClassesUpdateRequest):
    classes_file = WORKSPACE_DIR / "datasets" / "labeling" / "classes.txt"
    with open(classes_file, "w", encoding="utf-8") as f:
        for cls in req.classes:
            f.write(f"{cls.strip()}\n")
    return {"status": "success", "message": "类别列表更新成功"}

# 7. 一键自动检测 (YOLO-seg)
@app.post("/api/labeling/auto_detect")
def auto_detect_polygons(req: Dict[str, str]):
    name = req.get("name")
    model_path = req.get("model_path") # 可选特定权重路径
    
    if not name:
        raise HTTPException(status_code=400, detail="图片名称缺失")
        
    image_path = WORKSPACE_DIR / "datasets" / "labeling" / "images" / name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
        
    try:
        model = predictor.get_yolo_model(model_path)
        results = model(str(image_path), conf=0.25)
        
        polygons = []
        if len(results) > 0:
            r = results[0]
            if r.masks is not None:
                xyn = r.masks.xyn
                cls_list = r.boxes.cls.tolist()
                for i, segment in enumerate(xyn):
                    if len(segment) >= 3:
                        pts = segment.tolist()
                        pts = simplify_polygon(pts)
                        polygons.append({
                            "class_id": int(cls_list[i]),
                            "points": pts
                        })
        return {"polygons": polygons}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动检测失败: {str(e)}")

# 7.1 获取可用的分割模型列表
@app.get("/api/labeling/models")
def get_labeling_models():
    """扫描 models 目录以及已训练 runs 目录下的所有分割权重（排除 sam 权重）"""
    models_dir = WORKSPACE_DIR / "models"
    runs_dir = WORKSPACE_DIR / "runs"
    
    models_dir.mkdir(parents=True, exist_ok=True)
    
    models_list = []
    
    # 1. 扫描 models 目录下的 pt 文件
    if models_dir.exists():
        for file in models_dir.iterdir():
            if file.is_file() and file.suffix.lower() == ".pt":
                if "sam" not in file.name.lower():
                    rel_path = f"models/{file.name}"
                    models_list.append({
                        "name": file.name,
                        "path": rel_path,
                        "type": "default" if file.name == "yolo26s-seg.pt" else "custom"
                    })
                    
    # 2. 递归扫描 runs 目录下的 pt 文件
    if runs_dir.exists():
        for file in runs_dir.rglob("*.pt"):
            if "sam" not in file.name.lower():
                try:
                    rel_path = file.relative_to(WORKSPACE_DIR).as_posix()
                except Exception:
                    rel_path = str(file)
                    
                display_name = file.name
                if file.name == "best.pt":
                    display_name = "best.pt (最佳权重)"
                elif file.name == "last.pt":
                    display_name = "last.pt (最新权重)"
                    
                models_list.append({
                    "name": f"{display_name} - {file.parent.parent.name}",
                    "path": rel_path,
                    "type": "trained"
                })
                
    return models_list

# 8. SAM 辅助点击预测
@app.post("/api/labeling/sam_predict")
def sam_predict_polygons(req: SAMPredictRequest):
    image_path = WORKSPACE_DIR / "datasets" / "labeling" / "images" / req.name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
        
    if not req.points:
        return {"polygons": []}
        
    try:
        sam = predictor.get_sam_model()
        results = sam(str(image_path), points=[req.points], labels=[req.labels])
        
        polygons = []
        if len(results) > 0 and results[0].masks is not None:
            for segment in results[0].masks.xyn:
                if len(segment) >= 3:
                    pts = segment.tolist()
                    pts = simplify_polygon(pts)
                    polygons.append(pts)
        return {"polygons": polygons}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAM 识别失败: {str(e)}")

@app.get("/api/logs")
async def get_logs_stream(request: Request):
    """通过 SSE (Server-Sent Events) 实时推送训练日志"""
    async def log_generator():
        log_path = Path(trainer.log_file)
        
        # 如果日志文件还没有创建，先等待
        retry_count = 0
        while not log_path.exists() and retry_count < 10:
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.5)
            retry_count += 1
            
        if not log_path.exists():
            yield "data: [SYSTEM] 等待训练日志启动...\n\n"
            
        # 开始读取
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # 首次连接直接返回最后 200 行日志，避免前端控制台太空白
            lines = f.readlines()
            for line in lines[-200:]:
                yield f"data: {line.rstrip()}\n\n"
                
            # 持续监听新增行
            while True:
                if await request.is_disconnected():
                    break
                
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    # 如果进程已经结束并且文件也读完了，就退出流
                    status = trainer.get_status()
                    if status["state"] not in ["preparing", "training"] and not line:
                        yield f"data: [SYSTEM] 日志推送结束。\n\n"
                        break
                    await asyncio.sleep(0.2)

    return StreamingResponse(
        log_generator(),
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# 静态资源挂载（当 web/dist 目录存在时生效，方便生产环境单端口部署）
web_dist_path = WORKSPACE_DIR / "web" / "dist"
if web_dist_path.exists():
    app.mount("/assets", StaticFiles(directory=str(web_dist_path / "assets")), name="assets")
    
    @app.get("/{rest_of_path:path}")
    async def serve_spa(rest_of_path: str):
        if rest_of_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API Endpoint Not Found")
        index_file = web_dist_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        raise HTTPException(status_code=404, detail="Frontend build missing index.html")

if __name__ == "__main__":
    import uvicorn
    
    # 禁用 Uvicorn 频繁的 HTTP 请求访问日志，避免轮询状态时终端被大批量 200 OK 刷屏
    log_config = uvicorn.config.LOGGING_CONFIG.copy()
    log_config["loggers"]["uvicorn.access"]["handlers"] = []
    log_config["loggers"]["uvicorn.access"]["propagate"] = False
    
    # 端口绑定为 9523
    uvicorn.run("main:app", host="0.0.0.0", port=9523, log_config=log_config, reload=True)
