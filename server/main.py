# -*- coding: utf-8 -*-
import os
import sys
import time
import gc
import asyncio
import psutil
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 将当前目录加入 Python Path 以确保模块导入
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trainer import YOLOTrainer

# 确定 server 目录与工作空间根目录
SERVER_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
WORKSPACE_DIR = SERVER_DIR.parent.resolve()

def load_server_config() -> Dict[str, Any]:
    """
    加载 server/config.json 配置文件。
    若文件不存在或格式不正确，返回默认空配置，绝不抛出异常。
    支持相对路径（相对当前 server 目录）与绝对路径。
    """
    config_file = SERVER_DIR / "config.json"
    default_config = {
        "extra_model_paths": {
            "segment": [],
            "world": []
        }
    }
    if not config_file.exists():
        return default_config
    
    try:
        import json
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        extra = data.get("extra_model_paths", {})
        
        # 规整化为 Path 对象列表
        def to_path_list(val) -> List[Path]:
            if not val:
                return []
            if isinstance(val, str):
                val = [val]
            paths = []
            for p in val:
                if not p or not isinstance(p, str):
                    continue
                path_obj = Path(p.strip())
                # 若为相对路径，则以 SERVER_DIR（即当前 server 目录）为基准解析
                if not path_obj.is_absolute():
                    resolved_path = (SERVER_DIR / path_obj).resolve()
                else:
                    resolved_path = path_obj.resolve()
                paths.append(resolved_path)
            return paths

        return {
            "extra_model_paths": {
                "segment": to_path_list(extra.get("segment")),
                "world": to_path_list(extra.get("world"))
            }
        }
    except Exception as e:
        print(f"[Config] 加载 config.json 异常，已安全回退默认配置: {e}")
        return default_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 现代生命周期上下文管理器：替代已弃用的 @app.on_event("startup"/"shutdown")
    """
    global _model_cleanup_task
    # 服务启动阶段：拉起模型空闲检测与自动卸载任务
    if "_model_cleanup_loop" in globals():
        _model_cleanup_task = asyncio.create_task(_model_cleanup_loop())
        print(f"[ModelManager] 后台模型空闲清理任务已启动 (空闲超时: {MODEL_IDLE_TIMEOUT}s)")
    try:
        yield
    finally:
        # 服务关闭阶段：取消后台清理协程
        if _model_cleanup_task:
            _model_cleanup_task.cancel()
            try:
                await _model_cleanup_task
            except asyncio.CancelledError:
                pass
        # 释放所有模型，回收显存与内存
        if "predictor" in globals():
            predictor.unload_idle_models(timeout=0)
        print("[ModelManager] 所有模型已卸载，后台清理任务已停止")

app = FastAPI(title="YOLO26s-seg 训练控制台后端 API", lifespan=lifespan)

# 配置 CORS 允许跨域（前端 Vite 默认端口 5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源访问，便于局域网/多服务器部署调试
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 自动迁移旧的数据集结构到子目录 default/ 下
def migrate_legacy_dataset():
    legacy_labeling_dir = WORKSPACE_DIR / "datasets" / "labeling"
    legacy_images_dir = legacy_labeling_dir / "images"
    legacy_labels_dir = legacy_labeling_dir / "labels"
    legacy_classes_file = legacy_labeling_dir / "classes.txt"

    # 如果存在旧的 images 目录，并且它是一个文件夹（不是子数据集的 default）
    if legacy_images_dir.exists() and legacy_images_dir.is_dir():
        import shutil
        default_dataset_dir = legacy_labeling_dir / "default"
        default_images_dir = default_dataset_dir / "images"
        default_labels_dir = default_dataset_dir / "labels"
        default_classes_file = default_dataset_dir / "classes.txt"

        print(f"检测到旧版标注数据集，正在执行迁移到 default 数据集目录...")
        default_dataset_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 移动 images 目录
            if not default_images_dir.exists():
                shutil.move(str(legacy_images_dir), str(default_images_dir))
            else:
                for item in legacy_images_dir.iterdir():
                    shutil.move(str(item), str(default_images_dir / item.name))
                shutil.rmtree(legacy_images_dir)

            # 移动 labels 目录
            if legacy_labels_dir.exists():
                if not default_labels_dir.exists():
                    shutil.move(str(legacy_labels_dir), str(default_labels_dir))
                else:
                    for item in legacy_labels_dir.iterdir():
                        shutil.move(str(item), str(default_labels_dir / item.name))
                    shutil.rmtree(legacy_labels_dir)

            # 移动 classes.txt
            if legacy_classes_file.exists():
                if not default_classes_file.exists():
                    shutil.move(str(legacy_classes_file), str(default_classes_file))
                else:
                    legacy_classes_file.unlink()
            print(f"旧版数据集迁移成功！新路径：{default_dataset_dir}")
        except Exception as e:
            print(f"迁移旧数据集失败: {e}")

# 执行迁移
migrate_legacy_dataset()

# 确保最少有一个 default 数据集存在
labeling_dir = WORKSPACE_DIR / "datasets" / "labeling"
default_dir = labeling_dir / "default"
default_images_dir = default_dir / "images"
default_labels_dir = default_dir / "labels"
default_classes_file = default_dir / "classes.txt"

default_images_dir.mkdir(parents=True, exist_ok=True)
default_labels_dir.mkdir(parents=True, exist_ok=True)
if not default_classes_file.exists():
    with open(default_classes_file, "w", encoding="utf-8") as f:
        f.write("pig\n")

# 挂载标注图片静态资源（使得前端可以直接渲染整个 labeling 下所有子数据集的图片）
app.mount("/labeling_images", StaticFiles(directory=str(labeling_dir)), name="labeling_images")

# 初始化训练管理器
trainer = YOLOTrainer(str(WORKSPACE_DIR))

# 请求体结构校验模型
class TrainStartRequest(BaseModel):
    model_path: Optional[str] = Field(default="models/segment/yolo26s-seg.pt", description="训练基础模型权重路径")
    epochs: int = Field(default=300, ge=1, le=10000, description="训练轮次")
    batch: int = Field(default=4, ge=1, le=256, description="批次大小")
    lr0: float = Field(default=0.001, gt=0.0, le=1.0, description="初始学习率")
    patience: int = Field(default=50, ge=0, description="早停耐心值")
    imgsz: int = Field(default=960, ge=32, le=2048, description="输入图像尺寸")
    device: str = Field(default="0", description="训练设备：cpu, 0, 1, 0,1 等")
    split_ratio: str = Field(default="8:1:1", description="数据集划分比例 (train:val:test)")
    dataset: str = Field(default="default", description="训练选择的数据集")
    force_re_split: bool = Field(default=False, description="是否强制重新随机划分数据集（若为 False 则沿用历史划分增量追加）")
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
    status = trainer.get_status()
    # 如果没在训练，则获取最近一次训练的历史结果指标
    if status["state"] not in ["preparing", "training"]:
        status["last_run"] = trainer.get_last_run_info()
    return status

@app.get("/api/download_best")
def download_best_weight():
    """下载最近一次训练生成的最佳权重文件 best.pt"""
    run_dirs = [
        WORKSPACE_DIR / "runs" / "yolo26s_train",
        WORKSPACE_DIR / "runs" / "segment" / "yolo26s_train"
    ]
    
    best_pt = None
    for d in run_dirs:
        p = d / "weights" / "best.pt"
        if p.exists():
            best_pt = p
            break
            
    if not best_pt:
        raise HTTPException(status_code=404, detail="最佳权重文件 best.pt 不存在")
        
    return FileResponse(
        path=str(best_pt),
        filename="best.pt",
        media_type="application/octet-stream"
    )

# ==========================================
# 数据集管理接口
# ==========================================

@app.get("/api/labeling/datasets")
def get_datasets():
    labeling_dir = WORKSPACE_DIR / "datasets" / "labeling"
    labeling_dir.mkdir(parents=True, exist_ok=True)
    
    datasets = []
    for item in labeling_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            if (item / "images").exists() or item.name == "default":
                datasets.append(item.name)
    
    if "default" in datasets:
        datasets.remove("default")
        datasets.insert(0, "default")
    else:
        datasets.insert(0, "default")
        
    return {"datasets": datasets}

class CreateDatasetRequest(BaseModel):
    name: str = Field(..., description="数据集名称，仅限字母、数字、下划线、连字符和中文")

@app.post("/api/labeling/datasets")
def create_dataset(req: CreateDatasetRequest):
    import re
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="数据集名称不能为空")
    
    if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_-]+$', name):
        raise HTTPException(status_code=400, detail="数据集名称仅能包含中文、字母、数字、下划线和连字符")
        
    if name in ["images", "labels", "classes.txt", "temp_config.json", "temp_run.py", "processed"]:
        raise HTTPException(status_code=400, detail="不能使用保留词作为数据集名称")
        
    dataset_path = WORKSPACE_DIR / "datasets" / "labeling" / name
    if dataset_path.exists():
        raise HTTPException(status_code=400, detail="该数据集名称已存在")
        
    try:
        (dataset_path / "images").mkdir(parents=True, exist_ok=True)
        (dataset_path / "labels").mkdir(parents=True, exist_ok=True)
        with open(dataset_path / "classes.txt", "w", encoding="utf-8") as f:
            f.write("pig\n")
            
        return {"status": "success", "message": f"数据集 '{name}' 创建成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建数据集失败: {str(e)}")

@app.get("/api/sysinfo")
def get_sysinfo(dataset: str = "default"):
    """获取服务器系统硬件和数据集概要信息"""
    # 1. 硬件信息
    cpu_percent = psutil.cpu_percent(interval=None)
    # 使用当前进程 RSS 内存，而非系统全局内存
    # 这样能真实反映模型加载/卸载对服务进程的内存影响
    process = psutil.Process()
    proc_mem = process.memory_info()
    proc_mem_used_gb = round(proc_mem.rss / (1024 ** 3), 2)
    sys_memory = psutil.virtual_memory()
    
    # 2. GPU 显存与硬件信息精准采集
    gpu_available = False
    gpu_name = "N/A"
    gpu_memory_used_gb = 0.0
    gpu_memory_total_gb = 0.0
    gpu_memory_percent = 0.0
    gpu_memory_used_mb = 0.0
    gpu_memory_total_mb = 0.0

    # 优先方案：通过 PyTorch 的 CUDA 驱动底层接口获取整卡物理显存
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_name = torch.cuda.get_device_name(0)
            try:
                # mem_get_info 返回 (free_bytes, total_bytes)，反映整张显卡真实物理显存
                # 能真实统计训练子进程、推理进程以及后台任务的显存占用
                free_bytes, total_bytes = torch.cuda.mem_get_info(0)
                used_bytes = max(0, total_bytes - free_bytes)

                gpu_memory_total_gb = round(total_bytes / (1024 ** 3), 2)
                gpu_memory_used_gb = round(used_bytes / (1024 ** 3), 2)
                gpu_memory_percent = round((used_bytes / total_bytes) * 100, 1) if total_bytes > 0 else 0.0

                gpu_memory_used_mb = round(used_bytes / (1024 ** 2), 1)
                gpu_memory_total_mb = round(total_bytes / (1024 ** 2), 1)
            except Exception:
                # 兜底：使用 PyTorch 设备属性总显存与分配/保留显存
                total_mem = torch.cuda.get_device_properties(0).total_mem
                alloc_mem = torch.cuda.memory_allocated(0)
                reserved_mem = torch.cuda.memory_reserved(0)
                used_mem = max(alloc_mem, reserved_mem)

                gpu_memory_total_gb = round(total_mem / (1024 ** 3), 2)
                gpu_memory_used_gb = round(used_mem / (1024 ** 3), 2)
                gpu_memory_percent = round((used_mem / total_mem) * 100, 1) if total_mem > 0 else 0.0

                gpu_memory_used_mb = round(used_mem / (1024 ** 2), 1)
                gpu_memory_total_mb = round(total_mem / (1024 ** 2), 1)
    except Exception:
        pass

    # 兜底方案：如果 PyTorch 未能识别到 CUDA，但系统有 NVIDIA 驱动与 nvidia-smi
    if not gpu_available:
        try:
            import subprocess
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=1
            )
            if res.returncode == 0 and res.stdout.strip():
                first_line = res.stdout.strip().split("\n")[0]
                parts = [p.strip() for p in first_line.split(",")]
                if len(parts) >= 3:
                    gpu_name = parts[0]
                    used_mb = float(parts[1])
                    total_mb = float(parts[2])
                    gpu_available = True
                    gpu_memory_used_mb = round(used_mb, 1)
                    gpu_memory_total_mb = round(total_mb, 1)
                    gpu_memory_used_gb = round(used_mb / 1024, 2)
                    gpu_memory_total_gb = round(total_mb / 1024, 2)
                    gpu_memory_percent = round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0.0
        except Exception:
            pass

    # 3. 数据集状态判定 (zip 或者是本地标注目录)
    zip_file = WORKSPACE_DIR / "datasets" / "赶猪通道图集_yolo.zip"
    local_img_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images"

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
        dataset_path_str = f"本地标注数据集 [{dataset}] ({local_images_count}张图片)"

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": sys_memory.percent,
        "memory_used_gb": proc_mem_used_gb,
        "sys_memory_used_gb": round(sys_memory.used / (1024 ** 3), 2),
        "memory_total_gb": round(sys_memory.total / (1024 ** 3), 2),
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
        "gpu_memory_used_gb": gpu_memory_used_gb,
        "gpu_memory_total_gb": gpu_memory_total_gb,
        "gpu_memory_percent": gpu_memory_percent,
        "gpu_memory_used_mb": gpu_memory_used_mb,
        "gpu_memory_total_mb": gpu_memory_total_mb,
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

class SaveNegativeRequest(BaseModel):
    name: str

class SAMPredictRequest(BaseModel):
    name: str
    points: List[List[float]] = Field(..., description="点击坐标 [[x1, y1], ...]")
    labels: List[int] = Field(..., description="点击类型 [1, 0, ...]")

class PromptDetectRequest(BaseModel):
    name: str = Field(..., description="图片文件名")
    prompt: str = Field(..., description="提示词文本，如 'pig' 或 'pig, person'")
    conf: float = Field(default=0.25, ge=0.01, le=1.0, description="置信度阈值")
    class_id: int = Field(default=0, ge=0, description="默认分类索引 ID")
    model_path: Optional[str] = Field(default=None, description="指定的世界模型路径")
    use_sam: bool = Field(default=True, description="是否使用 SAM 模型进行高清边缘分割优化")

class SAMRefineRequest(BaseModel):
    name: str = Field(..., description="图片文件名")
    polygons: List[PolygonItem] = Field(..., description="待优化的多边形列表，包含 class_id 与 points")
    padding: float = Field(default=0.03, ge=0.0, le=0.2, description="外接矩形框外扩比例，防止边缘截断")


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

# 模型空闲自动卸载超时时间（秒），默认 5 分钟无使用则从内存中释放
MODEL_IDLE_TIMEOUT = int(os.environ.get("MODEL_IDLE_TIMEOUT", 300))

class LabelingPredictor:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        # 最大允许同时常驻显存/内存的模型数量（默认 2 个）
        # 设置为 1 时即为“单模型独占模式（每次换新模型自动清旧模型）”；
        # 设置为 2 时即为“LRU 缓存模式（最多常驻 2 个，超出自动踢出最久未使用的模型）”
        self.max_loaded_models = 2

        # 统一模型注册表：key -> Dict[str, Any]
        # key 格式形如：'yolo_seg:/abs/path', 'yolo_world:/abs/path', 'sam:/abs/path', 'sam3:/abs/path'
        self.loaded_models: Dict[str, Dict[str, Any]] = {}

        # 兼容旧属性结构
        self.yolo_models = {}
        self.yolo_world_models = {}
        self.sam_model = None
        self.sam3_models = {}
        self._last_used = {
            "yolo": 0.0,
            "yolo_world": 0.0,
            "sam": 0.0,
            "sam3": 0.0,
        }

    def _touch(self, model_type: str):
        """更新指定模型类型的最后使用时间"""
        self._last_used[model_type] = time.time()

    def _ensure_capacity(self, upcoming_key: str):
        """
        准备挂载容量：若即将加载的模型不在当前缓存中，且当前挂载数已达上限，
        则依据 LRU（最近最少使用）算法自动淘汰并卸载最久未访问的模型。
        """
        if upcoming_key in self.loaded_models:
            return  # 命中缓存，无需淘汰

        while len(self.loaded_models) >= self.max_loaded_models:
            # 找到 last_used_at 最小的条目（即最久未使用的模型）
            lru_key = min(self.loaded_models.keys(), key=lambda k: self.loaded_models[k].get("last_used_at", 0))
            lru_entry = self.loaded_models[lru_key]
            print(f"[ModelManager] 达到最大挂载上限 ({self.max_loaded_models})，触发 LRU 自动淘汰释放: {lru_entry['name']} ({lru_entry['type_display']})")
            self.unload_model_by_key(lru_key)

    def _register_model(self, key: str, name: str, model_type: str, type_display: str, path: str, instance: Any):
        """将新加载的模型注册进统一模型管理器并同步更新时间戳"""
        now = time.time()
        self.loaded_models[key] = {
            "key": key,
            "name": name,
            "type": model_type,
            "type_display": type_display,
            "path": path,
            "instance": instance,
            "loaded_at": now,
            "last_used_at": now
        }
        # 同步兼容旧属性
        if model_type == "yolo_seg":
            self.yolo_models[path] = instance
        elif model_type == "yolo_world":
            self.yolo_world_models[path] = instance
        elif model_type == "sam":
            self.sam_model = instance
        elif model_type == "sam3":
            self.sam3_models[path] = instance
        self._touch(model_type)

    def touch_model(self, key: str):
        """刷新模型访问时间"""
        if key in self.loaded_models:
            self.loaded_models[key]["last_used_at"] = time.time()
            self._touch(self.loaded_models[key]["type"])

    def unload_model_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        """按 key 卸载单个模型，释放对象引用并执行显存/内存物理回收"""
        if key not in self.loaded_models:
            return None

        entry = self.loaded_models.pop(key)
        path = entry.get("path", "")
        mtype = entry.get("type", "")

        # 释放实例
        if "instance" in entry:
            del entry["instance"]

        # 同步清理旧结构
        if mtype == "yolo_seg":
            self.yolo_models.pop(path, None)
        elif mtype == "yolo_world":
            self.yolo_world_models.pop(path, None)
            self.yolo_world_models.pop("__default__", None)
        elif mtype == "sam":
            self.sam_model = None
        elif mtype == "sam3":
            self.sam3_models.pop(path, None)

        # 显式垃圾回收与清空 CUDA 缓存
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        print(f"[ModelManager] 已卸载模型: {entry['name']} ({entry['type_display']})")
        return entry

    def unload_idle_models(self, timeout: int = None) -> List[str]:
        """
        卸载超过空闲超时的模型。
        timeout 为 None 时使用全局 MODEL_IDLE_TIMEOUT（默认 300 秒）。
        timeout 为 0 时强制卸载全部模型。
        """
        if timeout is None:
            timeout = MODEL_IDLE_TIMEOUT

        now = time.time()
        keys_to_unload = []
        for k, m in list(self.loaded_models.items()):
            idle = now - m.get("last_used_at", 0)
            if timeout == 0 or idle > timeout:
                keys_to_unload.append(k)

        unloaded_names = []
        for k in keys_to_unload:
            entry = self.unload_model_by_key(k)
            if entry:
                idle_sec = int(now - entry.get("last_used_at", now))
                unloaded_names.append(f"{entry['name']} (空闲 {idle_sec}s)")

        return unloaded_names

    def get_loaded_models_list(self) -> List[Dict[str, Any]]:
        """获取当前已挂载的模型列表（包含空闲时间和类型）"""
        now = time.time()
        result = []
        for k, m in self.loaded_models.items():
            idle = int(now - m.get("last_used_at", now))
            result.append({
                "key": m["key"],
                "name": m["name"],
                "type": m["type"],
                "type_display": m["type_display"],
                "path": m["path"],
                "loaded_at": m["loaded_at"],
                "last_used_at": m["last_used_at"],
                "idle_seconds": idle
            })
        result.sort(key=lambda x: x["last_used_at"], reverse=True)
        return result

    def set_max_loaded_models(self, max_models: int) -> int:
        """设置最大允许同时挂载的模型数量"""
        self.max_loaded_models = max(1, min(10, max_models))
        # 若调小容量后已加载数超出，立即按 LRU 顺序驱逐多余模型
        while len(self.loaded_models) > self.max_loaded_models:
            lru_key = min(self.loaded_models.keys(), key=lambda k: self.loaded_models[k].get("last_used_at", 0))
            self.unload_model_by_key(lru_key)
        return self.max_loaded_models

    def get_loaded_info(self) -> Dict[str, Any]:
        """兼容旧版状态查询接口"""
        now = time.time()
        info = {}
        for m in self.loaded_models.values():
            mtype = m["type"]
            info[mtype] = {
                "loaded": True,
                "name": m["name"],
                "idle_seconds": int(now - m.get("last_used_at", now))
            }
        return info

    def get_yolo_world_model(self, custom_path: str = None):
        from ultralytics import YOLOWorld

        # 1. 若指定了模型路径
        if custom_path and custom_path.strip():
            path_obj = Path(custom_path.strip())
            if not path_obj.is_absolute():
                full_path = (self.workspace_dir / path_obj).resolve()
            else:
                full_path = path_obj.resolve()

            full_path_str = str(full_path)
            model_key = f"yolo_world:{full_path_str}"
            model_name = full_path.name

            if model_key in self.loaded_models:
                self.touch_model(model_key)
                return self.loaded_models[model_key]["instance"]

            if not full_path.exists():
                raise FileNotFoundError(f"指定的世界模型权重不存在: {full_path.name}")

            self._ensure_capacity(model_key)

            if full_path.suffix.lower() == ".pth":
                try:
                    print(f"[YOLOWorld] 正在加载世界模型权重: {full_path.name}")
                    model = YOLOWorld(full_path_str)
                except Exception as load_err:
                    raise RuntimeError(
                        f"无法直接通过 Ultralytics 加载权重 '{full_path.name}' ({load_err})。"
                        f"若该模型为 CountGD / Grounding DINO 结构，需要安装相应的模型定义库。"
                    )
            else:
                print(f"[YOLOWorld] 正在加载世界模型权重: {full_path.name}")
                model = YOLOWorld(full_path_str)

            self._register_model(model_key, model_name, "yolo_world", "YOLO-World", full_path_str, model)
            return model

        # 2. 默认模型查找策略
        default_key = "yolo_world:__default__"
        if default_key in self.loaded_models:
            self.touch_model(default_key)
            return self.loaded_models[default_key]["instance"]

        candidate_names = [
            "yolov8m-worldv2.pt",
            "yolov8s-worldv2.pt",
            "yolov8l-worldv2.pt",
            "yolov8x-worldv2.pt",
            "yolov8m-world.pt",
            "yolov8s-world.pt",
            "yolov8l-world.pt",
            "yolov8x-world.pt"
        ]
        found_path = None
        models_dir = self.workspace_dir / "models"
        world_sub_dir = models_dir / "world"
        for name in candidate_names:
            p_sub = world_sub_dir / name
            if p_sub.exists():
                found_path = p_sub
                break
            p = models_dir / name
            if p.exists():
                found_path = p
                break

        self._ensure_capacity(default_key)
        if found_path:
            print(f"[YOLOWorld] 正在加载本地已下载权重: {found_path.name}")
            model = YOLOWorld(str(found_path))
            model_name = found_path.name
            path_str = str(found_path.resolve())
        else:
            print("[YOLOWorld] 未在 models/ 或 models/world/ 目录下找到本地 YOLO-World 权重，将尝试网络在线加载/下载 yolov8m-worldv2.pt...")
            model = YOLOWorld("yolov8m-worldv2.pt")
            model_name = "yolov8m-worldv2.pt"
            path_str = "yolov8m-worldv2.pt"

        self._register_model(default_key, model_name, "yolo_world", "YOLO-World", path_str, model)
        return model

    def get_yolo_model(self, custom_path: str = None):
        from ultralytics import YOLO

        # 1. 如果传入了特定模型路径
        if custom_path:
            path_obj = Path(custom_path)
            if not path_obj.is_absolute():
                full_path = (self.workspace_dir / path_obj).resolve()
            else:
                full_path = path_obj.resolve()

            full_path_str = str(full_path)
            model_key = f"yolo_seg:{full_path_str}"
            model_name = full_path.name

            if model_key in self.loaded_models:
                self.touch_model(model_key)
                return self.loaded_models[model_key]["instance"]

            if not full_path.exists():
                raise FileNotFoundError(f"指定的模型权重不存在: {full_path.name}")

            self._ensure_capacity(model_key)
            print(f"[YOLO-seg] 正在加载分割模型权重: {model_name}")
            model = YOLO(full_path_str)
            self._register_model(model_key, model_name, "yolo_seg", "YOLO分割", full_path_str, model)
            return model

        # 2. 默认模型加载逻辑
        best_pt = None
        for d in [self.workspace_dir / "runs" / "yolo26s_train", self.workspace_dir / "runs" / "segment" / "yolo26s_train"]:
            p = d / "weights" / "best.pt"
            if p.exists():
                best_pt = p
                break

        if best_pt:
            default_path = best_pt
        else:
            seg_path = self.workspace_dir / "models" / "segment" / "yolo26s-seg.pt"
            if seg_path.exists():
                default_path = seg_path
            else:
                default_path = self.workspace_dir / "models" / "yolo26s-seg.pt"

        default_path_str = str(default_path.resolve())
        model_key = f"yolo_seg:{default_path_str}"
        model_name = default_path.name

        if model_key in self.loaded_models:
            self.touch_model(model_key)
            return self.loaded_models[model_key]["instance"]

        if not default_path.exists():
            raise FileNotFoundError(f"默认模型权重不存在: {default_path.name}")

        self._ensure_capacity(model_key)
        print(f"[YOLO-seg] 正在加载默认分割模型权重: {model_name}")
        model = YOLO(default_path_str)
        self._register_model(model_key, model_name, "yolo_seg", "YOLO分割", default_path_str, model)
        return model

    def get_sam_model(self):
        from ultralytics import SAM
        sam_names = [
            "sam2.1_b.pt", 
            "sam3.1_multiplex.pt", 
            "sam3.1.pt", 
            "sam3.pt", 
            "sam_b.pt", 
            "mobile_sam.pt", 
            "sam2.1_t.pt"
        ]
        found_path = None
        models_dir = self.workspace_dir / "models"
        sam_sub_dir = models_dir / "sam"
        for name in sam_names:
            p_sub = sam_sub_dir / name
            if p_sub.exists():
                found_path = p_sub
                break
            p = models_dir / name
            if p.exists():
                found_path = p
                break
        if found_path is None:
            raise FileNotFoundError("未在 models/ 或 models/sam/ 目录下检测到 SAM 权重 (例如 sam3.1_multiplex.pt、sam3.pt、sam2.1_b.pt、mobile_sam.pt)。")

        full_path_str = str(found_path.resolve())
        model_key = f"sam:{full_path_str}"
        model_name = found_path.name

        if model_key in self.loaded_models:
            self.touch_model(model_key)
            return self.loaded_models[model_key]["instance"]

        self._ensure_capacity(model_key)
        print(f"[SAM] 正在加载 SAM 辅助分割权重: {model_name}")
        model = SAM(str(found_path))
        self._register_model(model_key, model_name, "sam", "SAM辅助分割", full_path_str, model)
        return model

    def get_sam3_model(self, model_path: str):
        import torch
        from ultralytics.models.sam.build_sam3 import build_sam3_image_model

        path_obj = Path(model_path.strip())
        if not path_obj.is_absolute():
            full_path = (self.workspace_dir / path_obj).resolve()
        else:
            full_path = path_obj.resolve()

        full_path_str = str(full_path)
        model_key = f"sam3:{full_path_str}"
        model_name = full_path.name

        if model_key in self.loaded_models:
            self.touch_model(model_key)
            return self.loaded_models[model_key]["instance"]

        if not full_path.exists():
            raise FileNotFoundError(f"指定的 SAM 3 模型权重不存在: {full_path.name}")

        self._ensure_capacity(model_key)
        print(f"[SAM3] 正在加载 SAM 3 文本推理(Semantic)模型: {model_name}")
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        model = build_sam3_image_model(full_path_str)
        model.to(device)
        model.eval()

        self._register_model(model_key, model_name, "sam3", "SAM3概念分割", full_path_str, model)
        return model

predictor = LabelingPredictor(WORKSPACE_DIR)

# 后台定时任务：每 60 秒检查一次，卸载超过空闲超时的模型
_model_cleanup_task = None

async def _model_cleanup_loop():
    """后台协程：周期性检查并卸载空闲模型"""
    while True:
        await asyncio.sleep(60)  # 每 60 秒扫描一次
        try:
            predictor.unload_idle_models()
        except Exception as e:
            print(f"[ModelManager] 后台清理异常: {e}")

class UnloadSpecificModelRequest(BaseModel):
    model_key: str = Field(..., description="要卸载的模型唯一 key")

class SetMaxLoadedModelsRequest(BaseModel):
    max_models: int = Field(default=2, ge=1, le=10, description="允许同时挂载的最大模型数量")

@app.get("/api/labeling/loaded_models")
def get_loaded_models():
    """查询当前常驻显存/内存中的模型清单及挂载上限配置"""
    return {
        "status": "success",
        "max_loaded_models": predictor.max_loaded_models,
        "loaded_count": len(predictor.loaded_models),
        "models": predictor.get_loaded_models_list()
    }

@app.post("/api/labeling/unload_specific_model")
def unload_specific_model(req: UnloadSpecificModelRequest):
    """指定卸载某个常驻模型，立即释放其占用的显存/内存"""
    entry = predictor.unload_model_by_key(req.model_key)
    if entry:
        return {
            "status": "success",
            "message": f"已成功卸载并释放模型: {entry['name']}",
            "unloaded_model": entry["name"],
            "max_loaded_models": predictor.max_loaded_models,
            "models": predictor.get_loaded_models_list()
        }
    return {
        "status": "warning",
        "message": "未找到指定的已加载模型或该模型已被释放",
        "max_loaded_models": predictor.max_loaded_models,
        "models": predictor.get_loaded_models_list()
    }

@app.post("/api/labeling/set_max_loaded_models")
def set_max_loaded_models(req: SetMaxLoadedModelsRequest):
    """设置最大允许同时挂载的模型数量（超出时将按 LRU 自动淘汰最久未使用的模型）"""
    actual_max = predictor.set_max_loaded_models(req.max_models)
    return {
        "status": "success",
        "message": f"已将模型挂载上限设置为 {actual_max} 个",
        "max_loaded_models": actual_max,
        "loaded_count": len(predictor.loaded_models),
        "models": predictor.get_loaded_models_list()
    }

@app.post("/api/labeling/unload_models")
def unload_models():
    """手动或页面退出时释放所有已加载的推理模型，立即回收显存/内存"""
    unloaded = predictor.unload_idle_models(timeout=0)
    if unloaded:
        print(f"[ModelManager] 接收到客户端退出/主动卸载请求，已即时释放模型: {', '.join(unloaded)}")
        return {
            "status": "success",
            "message": f"已释放模型: {', '.join(unloaded)}",
            "max_loaded_models": predictor.max_loaded_models,
            "models": []
        }
    return {
        "status": "success",
        "message": "当前没有已加载的模型",
        "max_loaded_models": predictor.max_loaded_models,
        "models": []
    }

@app.get("/api/labeling/model_status")
def get_model_status():
    """查询当前已加载模型的状态和空闲时间"""
    info = predictor.get_loaded_info()
    return {
        "idle_timeout": MODEL_IDLE_TIMEOUT,
        "max_loaded_models": predictor.max_loaded_models,
        "models": info,
        "loaded_list": predictor.get_loaded_models_list(),
        "any_loaded": len(predictor.loaded_models) > 0,
    }

# 1. 获取图片列表
@app.get("/api/labeling/images")
def get_labeling_images(dataset: str = "default"):
    image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    images_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images"
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "labels"
    
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    
    result = []
    for item in images_dir.iterdir():
        if item.is_file() and item.suffix.lower() in image_exts:
            # 检查是否有对应 label 文件
            label_name = item.stem + ".txt"
            label_path = labels_dir / label_name
            
            status = "unlabeled"
            label_count = 0
            labeled_mtime = 0
            if label_path.exists():
                try:
                    labeled_mtime = int(label_path.stat().st_mtime)
                except Exception:
                    labeled_mtime = 0

                if label_path.stat().st_size > 0:
                    try:
                        with open(label_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = [line.strip() for line in f if line.strip()]
                            label_count = len(lines)
                            status = "labeled" if label_count > 0 else "negative"
                    except Exception as e:
                        print(f"读取 label 文件行数出错 {label_path}: {e}")
                        status = "unlabeled"
                else:
                    status = "negative"
            
            result.append({
                "name": item.name,
                "labeled": status == "labeled",
                "status": status,
                "label_count": label_count,
                "size_kb": round(item.stat().st_size / 1024, 1),
                "mtime": int(item.stat().st_mtime),
                "labeled_mtime": labeled_mtime
            })
    # 按最后修改时间倒序排列
    result.sort(key=lambda x: x["mtime"], reverse=True)
    return result

# 2. 上传图片
@app.post("/api/labeling/upload")
async def upload_labeling_images(dataset: str = "default", files: List[UploadFile] = File(...)):
    images_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images"
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
def delete_labeling_image(name: str, dataset: str = "default"):
    images_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images"
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "labels"
    
    img_path = images_dir / name
    if img_path.exists():
        img_path.unlink()
        
    label_path = labels_dir / (Path(name).stem + ".txt")
    if label_path.exists():
        label_path.unlink()
        
    return {"status": "success", "message": f"图片 {name} 及其标签已被删除"}

# 4. 获取已有标注和 classes 列表
@app.get("/api/labeling/labels/{name}")
def get_labeling_labels(name: str, dataset: str = "default"):
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "labels"
    classes_file = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "classes.txt"
    
    labels_dir.mkdir(parents=True, exist_ok=True)
    classes_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 确保 classes.txt 存在
    if not classes_file.exists():
        with open(classes_file, "w", encoding="utf-8") as f:
            f.write("pig\n")
            
    classes = ["pig"]
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
# 5. 保存标注
@app.post("/api/labeling/save")
def save_labeling_labels(req: SaveAnnotationRequest, dataset: str = "default"):
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    
    label_path = labels_dir / (Path(req.name).stem + ".txt")
    
    valid_polygons = [poly for poly in req.polygons if len(poly.points) >= 3]
    
    if not valid_polygons:
        # 如果 polygons 为空，删除可能存在的标签文件（使其变成“未标”状态），而不是留个空文件被误判为负样本
        if label_path.exists():
            try:
                label_path.unlink()
            except Exception as e:
                print(f"删除旧标签文件失败 {label_path}: {e}")
        return {"status": "success", "message": f"{req.name} 标注已清空"}
    
    lines = []
    for poly in valid_polygons:
        coords_str = " ".join([f"{p[0]:.6f} {p[1]:.6f}" for p in poly.points])
        lines.append(f"{poly.class_id} {coords_str}\n")
        
    try:
        with open(label_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入标签文件失败: {str(e)}")
        
    labeled_mtime = int(label_path.stat().st_mtime) if label_path.exists() else int(time.time())
    return {
        "status": "success",
        "message": f"{req.name} 标注已保存",
        "labeled_mtime": labeled_mtime
    }

# 5.1 保存为负样本并重命名
@app.post("/api/labeling/save_negative")
def save_labeling_negative(req: SaveNegativeRequest, dataset: str = "default"):
    images_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images"
    labels_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "labels"
    
    img_path = images_dir / req.name
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
        
    suffix = img_path.suffix.lower()
    
    # 扫描所有图片文件，找出符合 负样本{number}{suffix} 的最大编号
    import re
    max_num = 0
    pattern = re.compile(r"^负样本(\d+)$")
    
    for item in images_dir.iterdir():
        if item.is_file() and item.suffix.lower() == suffix:
            match = pattern.match(item.stem)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
                    
    next_num = max_num + 1
    # 确保不与已有的图片和标签文件重名冲突
    while (images_dir / f"负样本{next_num}{suffix}").exists() or (labels_dir / f"负样本{next_num}.txt").exists():
        next_num += 1
        
    new_stem = f"负样本{next_num}"
    new_img_name = f"{new_stem}{suffix}"
    new_img_path = images_dir / new_img_name
    
    # 如果存在旧的标签文件，物理删除它
    old_label_path = labels_dir / (Path(req.name).stem + ".txt")
    if old_label_path.exists():
        try:
            old_label_path.unlink()
        except Exception as e:
            print(f"删除旧标签文件失败 {old_label_path}: {e}")
            
    # 重命名图片文件
    import shutil
    try:
        shutil.move(str(img_path), str(new_img_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片文件重命名失败: {str(e)}")
        
    # 创建新的空标签文件以代表负样本
    new_label_path = labels_dir / f"{new_stem}.txt"
    try:
        with open(new_label_path, "w", encoding="utf-8") as f:
            pass  # 创建空文件
    except Exception as e:
        # 回退图片重命名
        if new_img_path.exists():
            try:
                shutil.move(str(new_img_path), str(img_path))
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"创建空标签文件失败: {str(e)}")
        
    return {
        "status": "success",
        "message": f"已成功保存为负样本并重命名为 {new_img_name}",
        "new_name": new_img_name,
        "labeled_mtime": int(new_label_path.stat().st_mtime) if new_label_path.exists() else int(time.time())
    }

# 6. 获取和更新 Classes，并提供级联标签删除清洗
@app.get("/api/labeling/classes")
def get_labeling_classes(dataset: str = "default"):
    dataset_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset
    classes_file = dataset_dir / "classes.txt"
    
    if not classes_file.exists():
        classes_file.parent.mkdir(parents=True, exist_ok=True)
        with open(classes_file, "w", encoding="utf-8") as f:
            f.write("pig\n")
            
    classes = ["pig"]
    with open(classes_file, "r", encoding="utf-8", errors="ignore") as f:
        classes = [line.strip() for line in f if line.strip()]
    return {"classes": classes}

@app.post("/api/labeling/classes")
def update_labeling_classes(req: ClassesUpdateRequest, dataset: str = "default"):
    dataset_dir = WORKSPACE_DIR / "datasets" / "labeling" / dataset
    classes_file = dataset_dir / "classes.txt"
    labels_dir = dataset_dir / "labels"
    
    # 读取旧的类别
    old_classes = []
    if classes_file.exists():
        with open(classes_file, "r", encoding="utf-8", errors="ignore") as f:
            old_classes = [line.strip() for line in f if line.strip()]
            
    # 过滤空项
    new_classes = [cls.strip() for cls in req.classes if cls.strip()]
    if not new_classes:
        raise HTTPException(status_code=400, detail="类别列表不能为空，必须保留至少一个分类标签")
        
    # 比对新旧列表，找出被删除的类别索引
    deleted_indices = []
    for idx, old_cls in enumerate(old_classes):
        if old_cls not in new_classes:
            deleted_indices.append(idx)
            
    # 执行类别写入
    dataset_dir.mkdir(parents=True, exist_ok=True)
    with open(classes_file, "w", encoding="utf-8") as f:
        for cls in new_classes:
            f.write(f"{cls}\n")
            
    # 若有被删除的类别，且 labels 目录存在，对所有标注进行级联清洗
    if deleted_indices and labels_dir.exists():
        deleted_indices.sort(reverse=True)
        
        for label_file in labels_dir.glob("*.txt"):
            if not label_file.is_file():
                continue
            
            cleaned_lines = []
            modified = False
            try:
                with open(label_file, "r", encoding="utf-8", errors="ignore") as lf:
                    lines = lf.readlines()
                    
                for line in lines:
                    parts = line.strip().split()
                    if not parts:
                        continue
                    
                    try:
                        class_id = int(parts[0])
                    except ValueError:
                        cleaned_lines.append(line)
                        continue
                        
                    # 检查 class_id 是否是被删除的类别
                    if class_id in deleted_indices:
                        modified = True
                        continue
                    
                    # 调整大于被删类别的 class_id
                    shift = sum(1 for d_idx in deleted_indices if class_id > d_idx)
                    if shift > 0:
                        class_id -= shift
                        parts[0] = str(class_id)
                        modified = True
                        
                    cleaned_lines.append(" ".join(parts) + "\n")
                    
                # 如果发生修改，写回标签文件
                if modified:
                    if cleaned_lines:
                        with open(label_file, "w", encoding="utf-8") as lf:
                            lf.writelines(cleaned_lines)
                    else:
                        label_file.unlink()
            except Exception as e:
                print(f"清洗标签文件 {label_file.name} 出错: {e}")
                
    return {"status": "success", "message": "类别列表更新成功，标签清洗完毕"}

# 7. 一键自动检测 (YOLO-seg)
@app.post("/api/labeling/auto_detect")
def auto_detect_polygons(req: Dict[str, str], dataset: str = "default"):
    name = req.get("name")
    model_path = req.get("model_path") # 可选特定权重路径
    
    if not name:
        raise HTTPException(status_code=400, detail="图片名称缺失")
        
    image_path = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images" / name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    
    results = None
    try:
        import torch
        with torch.no_grad():
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
    finally:
        if results is not None:
            del results
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

# 7.1 获取可用的分割模型列表
@app.get("/api/labeling/models")
def get_labeling_models():
    """
    扫描 runs 训练产物目录、models/ (含 models/segment/) 目录以及 config.json 配置的 extra_model_paths.segment 目录下的所有分割权重。
    自动排除 SAM 交互分割权重与 YOLO-World 开放词汇模型。
    """
    cfg = load_server_config()
    extra_seg_dirs = cfg.get("extra_model_paths", {}).get("segment", [])
    
    models_dir = WORKSPACE_DIR / "models"
    segment_dir = models_dir / "segment"
    runs_dir = WORKSPACE_DIR / "runs"
    
    models_dir.mkdir(parents=True, exist_ok=True)
    
    models_list = []
    seen_paths = set()
    
    def is_seg_weight(filename: str) -> bool:
        fn_lower = filename.lower()
        if not (fn_lower.endswith(".pt") or fn_lower.endswith(".onnx") or fn_lower.endswith(".engine")):
            return False
        # 排除 SAM 系列与 YOLO-World 系列权重
        if "sam" in fn_lower or "world" in fn_lower:
            return False
        return True

    # 1. 递归扫描 runs 目录下的已训练 pt 文件 (优先展示训练权重)
    trained_models = []
    if runs_dir.exists():
        for file in runs_dir.rglob("*.pt"):
            if is_seg_weight(file.name):
                try:
                    rel_path = file.relative_to(WORKSPACE_DIR).as_posix()
                except Exception:
                    rel_path = str(file.resolve())
                    
                if rel_path in seen_paths:
                    continue
                seen_paths.add(rel_path)
                    
                display_name = file.name
                priority = 2
                if file.name == "best.pt":
                    display_name = "best.pt (最佳权重)"
                    priority = 0
                elif file.name == "last.pt":
                    display_name = "last.pt (最新权重)"
                    priority = 1
                    
                trained_models.append({
                    "name": display_name,
                    "path": rel_path,
                    "type": "trained",
                    "_priority": priority
                })
        # 训练模型按优先级排序 (best.pt > last.pt > 其他)
        trained_models.sort(key=lambda x: x["_priority"])
        for item in trained_models:
            item.pop("_priority", None)
            models_list.append(item)

    # 2. 扫描 models/segment 专有分类子目录下的 pt 文件
    if segment_dir.exists():
        for file in segment_dir.iterdir():
            if file.is_file() and is_seg_weight(file.name):
                rel_path = f"models/segment/{file.name}"
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    models_list.append({
                        "name": file.name,
                        "path": rel_path,
                        "type": "default" if file.name == "yolo26s-seg.pt" else "custom"
                    })

    # 3. 扫描 models 根目录下的 pt 文件 (兼容直接放置分割模型)
    if models_dir.exists():
        for file in models_dir.iterdir():
            if file.is_file() and is_seg_weight(file.name):
                rel_path = f"models/{file.name}"
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    models_list.append({
                        "name": file.name,
                        "path": rel_path,
                        "type": "default" if file.name == "yolo26s-seg.pt" else "custom"
                    })

    # 4. 扫描外部配置目录中的模型文件 (extra_model_paths.segment)
    for extra_dir in extra_seg_dirs:
        try:
            if extra_dir.exists() and extra_dir.is_dir():
                for file in extra_dir.iterdir():
                    if file.is_file() and is_seg_weight(file.name):
                        abs_path = str(file.resolve())
                        if abs_path not in seen_paths:
                            seen_paths.add(abs_path)
                            models_list.append({
                                "name": f"{file.name}",
                                "path": abs_path,
                                "type": "extra"
                            })
        except Exception as e:
            print(f"[ModelScan] 扫描外部分割目录 {extra_dir} 异常已安全忽略: {e}")
                    
    return models_list

# 7.2 获取可用的世界/开放词汇模型列表
@app.get("/api/labeling/world_models")
def get_labeling_world_models():
    """
    扫描 models/world/、models/ 目录以及 config.json 配置的 extra_model_paths.world 目录下的所有世界/开放词汇模型权重 (.pt, .pth)。
    """
    cfg = load_server_config()
    extra_world_dirs = cfg.get("extra_model_paths", {}).get("world", [])
    
    models_dir = WORKSPACE_DIR / "models"
    world_sub_dir = models_dir / "world"
    
    models_dir.mkdir(parents=True, exist_ok=True)
    
    world_models_list = []
    seen_paths = set()
    
    def is_world_weight(filename: str) -> bool:
        fn_lower = filename.lower()
        if not (fn_lower.endswith(".pt") or fn_lower.endswith(".pth")):
            return False
        # 排除普通的 SAM 权重，但保留 SAM 3（支持文本直推 PCS）
        if "sam" in fn_lower and "sam3" not in fn_lower:
            return False
        return True

    # 1. 扫描 models/world/ 子目录
    if world_sub_dir.exists() and world_sub_dir.is_dir():
        for file in world_sub_dir.iterdir():
            if file.is_file() and is_world_weight(file.name):
                rel_path = f"models/world/{file.name}"
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    world_models_list.append({
                        "name": file.name,
                        "path": rel_path,
                        "type": "custom"
                    })

    # 2. 扫描 models/ 根目录下包含 world 的权重
    if models_dir.exists() and models_dir.is_dir():
        for file in models_dir.iterdir():
            if file.is_file() and is_world_weight(file.name) and "world" in file.name.lower():
                rel_path = f"models/{file.name}"
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    world_models_list.append({
                        "name": file.name,
                        "path": rel_path,
                        "type": "custom"
                    })

    # 3. 扫描外部配置目录 (extra_model_paths.world)
    for extra_dir in extra_world_dirs:
        try:
            if extra_dir.exists() and extra_dir.is_dir():
                for file in extra_dir.iterdir():
                    if file.is_file() and is_world_weight(file.name):
                        abs_path = str(file.resolve())
                        if abs_path not in seen_paths:
                            seen_paths.add(abs_path)
                            world_models_list.append({
                                "name": f"{file.name}",
                                "path": abs_path,
                                "type": "extra"
                            })
        except Exception as e:
            print(f"[ModelScan] 扫描外部世界模型目录 {extra_dir} 异常已安全忽略: {e}")

    # 4. 扫描 models/sam/ 目录下的 SAM 3 权重（原生支持文本词汇输入的 PCS 分割模型）
    sam_sub_dir = models_dir / "sam"
    if sam_sub_dir.exists() and sam_sub_dir.is_dir():
        for file in sam_sub_dir.iterdir():
            if file.is_file() and file.name.lower().startswith("sam3") and file.name.lower().endswith(".pt"):
                rel_path = f"models/sam/{file.name}"
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    world_models_list.append({
                        "name": f"{file.name} (SAM3 文本分割)",
                        "path": rel_path,
                        "type": "sam3"
                    })

    # 如果没有任何本地或外部世界模型，提供默认回退选项
    if not world_models_list:
        world_models_list.append({
            "name": "yolov8m-worldv2.pt (默认内置/在线)",
            "path": "",
            "type": "default"
        })

    return world_models_list

# 8. SAM 辅助点击预测
@app.post("/api/labeling/sam_predict")
def sam_predict_polygons(req: SAMPredictRequest, dataset: str = "default"):
    image_path = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images" / req.name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
        
    if not req.points:
        return {"polygons": []}
    
    results = None
    try:
        import torch
        with torch.no_grad():
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
    finally:
        if results is not None:
            del results
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

# 8.1 基于 Prompt 开放词汇自动识别 (YOLO-World / SAM 3 + 可选 SAM 多边形提取)
@app.post("/api/labeling/prompt_detect")
def prompt_detect_polygons(req: PromptDetectRequest, dataset: str = "default"):
    image_path = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images" / req.name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
        
    prompt_str = req.prompt.strip()
    if not prompt_str:
        raise HTTPException(status_code=400, detail="提示词不能为空")
        
    prompts = [p.strip() for p in prompt_str.replace("，", ",").split(",") if p.strip()]
    if not prompts:
        raise HTTPException(status_code=400, detail="有效提示词不能为空")
    
    # 判断选中的模型是否为 SAM 3 系列（原生支持文本词汇输入）
    is_sam3_model = False
    if req.model_path:
        model_name_lower = Path(req.model_path).name.lower()
        is_sam3_model = model_name_lower.startswith("sam3") and model_name_lower.endswith(".pt")
    
    # 用于 finally 块中安全释放的局部变量
    results = None
    sam_results = None
        
    try:
        import torch
        import gc
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        
        # 推理前清理显存与垃圾碎片，降低 OOM 风险
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        # 禁用梯度计算，防止推理过程中构建计算图导致 tensor 累积泄漏
        with torch.no_grad():
            
            # ============================================
            # 分支 A: SAM 3 文本直推（一步到位检测+精细分割）
            # ============================================
            if is_sam3_model:
                # 获取或缓存 SAM 模型实例（已改为返回 semantic backbone 原生模型）
                sam3_model = predictor.get_sam3_model(req.model_path)
                print(f"[SAM3-PCS] 图片: {req.name}, 提示词: '{req.prompt}', 置信度阈值: {req.conf}, 使用 SAM 3 文本直推分割")
                
                from ultralytics.models.sam import SAM3SemanticPredictor
                
                # 配置覆盖，限制 imgsz 为 1008 避免高分辨率图直接推理导致 OOM
                overrides = {
                    "conf": req.conf,
                    "task": "segment",
                    "mode": "predict",
                    "model": req.model_path,
                    "device": device,
                    "imgsz": 1008,
                    "save": False,
                    "verbose": False
                }
                
                # 初始化专用语义分割预测器
                sam3_predictor = SAM3SemanticPredictor(overrides=overrides)
                
                # 复用已加载的底层 model 以避免重复从磁盘读取权重
                results = sam3_predictor(source=str(image_path), model=sam3_model, text=prompts)
                
                if len(results) == 0:
                    print(f"[SAM3-PCS] 未检测到任何匹配目标")
                    return {"polygons": []}
                
                r = results[0]
                polygons = []
                
                # SAM 3 直接返回 masks + boxes，提取归一化多边形
                if r.masks is not None and len(r.masks) > 0:
                    sam3_masks = r.masks.xyn
                    # 提取类别信息（SAM 3 的 boxes 最后一列为 cls）
                    cls_ids = r.boxes.cls.cpu().numpy().astype(int) if r.boxes is not None and r.boxes.cls is not None else None
                    conf_scores = r.boxes.conf.cpu().numpy() if r.boxes is not None and r.boxes.conf is not None else None
                    
                    for i, segment in enumerate(sam3_masks):
                        if len(segment) >= 3:
                            pts = simplify_polygon(segment.tolist())
                            # 确定标签：优先使用模型返回的类别索引映射到 prompts
                            label = prompts[0]
                            if cls_ids is not None and i < len(cls_ids):
                                cls_idx = int(cls_ids[i])
                                if cls_idx < len(prompts):
                                    label = prompts[cls_idx]
                            
                            conf_val = float(conf_scores[i]) if conf_scores is not None and i < len(conf_scores) else 1.0
                            polygons.append({
                                "class_id": req.class_id,
                                "points": pts,
                                "label": label,
                                "confidence": conf_val
                            })
                    
                    print(f"[SAM3-PCS] 成功分割 {len(polygons)} 个目标实例")
                else:
                    print(f"[SAM3-PCS] SAM 3 未生成有效 Mask")
                
                # 释放推理结果
                del r, results, sam3_predictor
                results = None
                
                return {"polygons": polygons}
            
            # ============================================
            # 分支 B: YOLO-World 两阶段流水线（检测 + 可选 SAM 优化）
            # ============================================
            # 1. 使用选定的 YOLO-World 开放词汇模型进行检测
            yolo_world = predictor.get_yolo_world_model(req.model_path)
            
            # 防御 PyTorch 在多轮更换 Prompt 时发生的 Device Mismatch 错误
            try:
                yolo_world.set_classes(prompts)
                if hasattr(yolo_world, 'model') and yolo_world.model is not None:
                    yolo_world.model.to(device)
                results = yolo_world(str(image_path), conf=req.conf, device=device)
            except Exception as device_err:
                if "same device" in str(device_err) or "cuda" in str(device_err).lower():
                    print(f"[PromptDetect] 自动恢复模型设备上下文: {device_err}")
                    # 先释放局部引用，确保旧模型可被 GC 回收
                    del yolo_world
                    if req.model_path and req.model_path in predictor.yolo_world_models:
                        predictor.yolo_world_models.pop(req.model_path, None)
                    else:
                        predictor.yolo_world_models.pop("__default__", None)
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    yolo_world = predictor.get_yolo_world_model(req.model_path)
                    yolo_world.set_classes(prompts)
                    if hasattr(yolo_world, 'model') and yolo_world.model is not None:
                        yolo_world.model.to(device)
                    results = yolo_world(str(image_path), conf=req.conf, device=device)
                else:
                    raise device_err
            
            if len(results) == 0 or len(results[0].boxes) == 0:
                print(f"[PromptDetect] 图片: {req.name}, 提示词: '{req.prompt}', 置信度阈值: {req.conf} -> 未检测到任何匹配目标 (boxes count: 0)")
                return {"polygons": []}
                
            r = results[0]
            # 立即提取所需数据到 CPU numpy，之后可安全释放 GPU tensor
            boxes_xyxy = r.boxes.xyxy.cpu().numpy() # [N, 4] 绝对像素坐标
            cls_ids = r.boxes.cls.cpu().numpy().astype(int) # [N] 对应 prompts 索引
            conf_scores = r.boxes.conf.cpu().numpy() # [N] 置信度得分
            img_h, img_w = r.orig_shape
            
            # 数据已提取完毕，立即释放 YOLO-World 推理结果以回收显存和内存
            del r, results
            results = None
            
            max_conf = float(conf_scores.max()) if len(conf_scores) > 0 else 0.0
            print(f"[PromptDetect] 图片: {req.name}, 提示词: '{req.prompt}', 置信度阈值: {req.conf}, use_sam={req.use_sam} -> 检测到 {len(boxes_xyxy)} 个目标, 最高置信度: {max_conf:.4f}")
            
            polygons = []
            
            # 2. 如果开启了 SAM 优化 (req.use_sam=True)，尝试使用 SAM 获取精细的多边形 Mask
            sam_available = False
            if req.use_sam:
                try:
                    sam = predictor.get_sam_model()
                    # 将检测到的 Boxes 传给 SAM 预测 Segmentation Mask
                    sam_results = sam(str(image_path), bboxes=boxes_xyxy.tolist())
                    if len(sam_results) > 0 and sam_results[0].masks is not None:
                        sam_masks = sam_results[0].masks.xyn
                        for i, segment in enumerate(sam_masks):
                            if len(segment) >= 3:
                                pts = simplify_polygon(segment.tolist())
                                conf_val = float(conf_scores[i]) if i < len(conf_scores) else 1.0
                                polygons.append({
                                    "class_id": req.class_id,
                                    "points": pts,
                                    "label": prompts[cls_ids[i]] if i < len(cls_ids) else prompts[0],
                                    "confidence": conf_val
                                })
                        sam_available = True
                except Exception as sam_err:
                    print(f"[PromptDetect] SAM 提拉 Mask 失败或模型未找到，改用矩形边界框: {sam_err}")
                    sam_available = False
                finally:
                    # 及时释放 SAM 推理结果
                    if sam_results is not None:
                        del sam_results
                        sam_results = None
                
            # 3. 若未开启 SAM 或 SAM 执行失败，使用 4 点归一化矩形框作为 Segmentation 多边形
            if not sam_available:
                for i, box in enumerate(boxes_xyxy):
                    x1, y1, x2, y2 = box
                    norm_box = [
                        [round(float(x1 / img_w), 6), round(float(y1 / img_h), 6)],
                        [round(float(x2 / img_w), 6), round(float(y1 / img_h), 6)],
                        [round(float(x2 / img_w), 6), round(float(y2 / img_h), 6)],
                        [round(float(x1 / img_w), 6), round(float(y2 / img_h), 6)]
                    ]
                    polygons.append({
                        "class_id": req.class_id,
                        "points": norm_box,
                        "label": prompts[cls_ids[i]] if i < len(cls_ids) else prompts[0]
                    })
                    
        return {"polygons": polygons}
    except Exception as e:
        err_msg = str(e)
        if "No module named 'clip'" in err_msg or "clip" in err_msg.lower():
            raise HTTPException(status_code=500, detail="缺少开放词汇文本编码依赖 'openai-clip'。请在服务器终端运行：pip install openai-clip")
        raise HTTPException(status_code=500, detail=f"Prompt 开放词汇识别失败: {err_msg}")
    finally:
        # 确保所有推理结果被释放，并强制触发 GC 回收
        try:
            if results is not None:
                del results
            if sam_results is not None:
                del sam_results
        except Exception:
            pass
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

# 8.2 SAM 实例边缘重分割优化 (Refine Polygons)
@app.post("/api/labeling/sam_refine")
def sam_refine_polygons(req: SAMRefineRequest, dataset: str = "default"):
    """
    根据已有多边形的外接矩形边界框，调用 SAM 模型重新进行超高精度的边缘分割，
    将模型直接检测出的粗糙多边形一键精修吸附到物体的真实物理边缘。
    """
    image_path = WORKSPACE_DIR / "datasets" / "labeling" / dataset / "images" / req.name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
        
    if not req.polygons:
        return {"polygons": [], "refined_count": 0}
        
    # 读取图片尺寸
    img = cv2.imread(str(image_path))
    if img is None:
        raise HTTPException(status_code=500, detail="无法读取图像数据")
    img_h, img_w = img.shape[:2]
    
    # 提取每个多边形的外接矩形框
    boxes_xyxy = []
    valid_indices = []
    
    for idx, poly in enumerate(req.polygons):
        if not poly.points or len(poly.points) < 3:
            continue
        xs = [p[0] for p in poly.points]
        ys = [p[1] for p in poly.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        w_box = max(max_x - min_x, 1e-4)
        h_box = max(max_y - min_y, 1e-4)
        
        pad_x = w_box * req.padding
        pad_y = h_box * req.padding
        
        x1 = max(0.0, min_x - pad_x) * img_w
        y1 = max(0.0, min_y - pad_y) * img_h
        x2 = min(1.0, max_x + pad_x) * img_w
        y2 = min(1.0, max_y + pad_y) * img_h
        
        boxes_xyxy.append([x1, y1, x2, y2])
        valid_indices.append(idx)
        
    if not boxes_xyxy:
        return {
            "status": "success",
            "polygons": [poly.model_dump() for poly in req.polygons],
            "refined_count": 0
        }
        
    sam_results = None
    try:
        import torch
        with torch.no_grad():
            sam = predictor.get_sam_model()
            # 批量传入 Bounding Box Prompts
            sam_results = sam(str(image_path), bboxes=boxes_xyxy)
            
            refined_polygons = [poly.model_dump() for poly in req.polygons]
            refined_count = 0
            
            if len(sam_results) > 0 and sam_results[0].masks is not None:
                sam_masks = sam_results[0].masks.xyn
                for b_idx, segment in enumerate(sam_masks):
                    if b_idx < len(valid_indices):
                        orig_idx = valid_indices[b_idx]
                        if len(segment) >= 3:
                            pts = simplify_polygon(segment.tolist())
                            refined_polygons[orig_idx]["points"] = pts
                            refined_count += 1
                            
        return {
            "status": "success",
            "polygons": refined_polygons,
            "refined_count": refined_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAM 优化失败: {str(e)}")
    finally:
        if sam_results is not None:
            del sam_results
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

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

# 挂载训练结果 runs 目录为静态资源，便于前端加载 results.png 等评估图表
runs_dir = WORKSPACE_DIR / "runs"
runs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/runs", StaticFiles(directory=str(runs_dir)), name="runs")

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
