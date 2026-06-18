# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import psutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
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
            # 通过 torch 无法非常准确获取全部显卡的总体剩余，但可以用 nvidia-smi 替代或者返回基本情况
            gpu_memory_used = torch.cuda.memory_allocated(0) / (1024 ** 2)  # MB
            # 这里简单返回是否可用和卡名称
    except Exception:
        pass

    # 2. 原始数据集状态
    zip_file = WORKSPACE_DIR / "datasets" / "赶猪通道图集_yolo.zip"
    dataset_status = "missing"
    dataset_size_mb = 0.0
    
    if zip_file.exists():
        dataset_status = "ready"
        dataset_size_mb = round(zip_file.stat().st_size / (1024 ** 2), 2)

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024 ** 3), 2),
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
        "dataset_status": dataset_status,
        "dataset_size_mb": dataset_size_mb,
        "dataset_path": zip_file.name if zip_file.exists() else "无"
    }

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
