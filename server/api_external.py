# -*- coding: utf-8 -*-
"""
第三方系统专用开放推理接口模块 (External Inference API)
提供面向第三方系统的目标分割模型识别与 Prompt 开放词汇识别能力。
支持 Multipart 表单文件直接上传与 Base64 编码 JSON 传参。
"""

import time
import base64
import gc
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

# 创建独立路由
router = APIRouter(
    prefix="/api/v1/inference",
    tags=["第三方开放推理接口 (External Inference API)"]
)

# 全局推理器与配置引用（由 main.py 初始化时注入）
_predictor = None
_workspace_dir = None


def init_external_api(predictor_instance, workspace_dir: Path):
    """
    初始化第三方开放接口，注入主服务的 Predictor 单例与工作空间路径。
    实现全局共享 LRU 模型缓存与显存管控。
    """
    global _predictor, _workspace_dir
    _predictor = predictor_instance
    _workspace_dir = workspace_dir


# ==============================================================================
# Pydantic 请求与响应模型定义
# ==============================================================================

class SegmentJsonRequest(BaseModel):
    """专用分割模型（YOLO-seg）Base64 请求体"""
    image_base64: str = Field(
        ...,
        description="图片 Base64 编码字符串，支持带有 data:image/jpeg;base64, 前缀或纯 base64 字符串",
        example="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    conf: float = Field(0.25, ge=0.01, le=1.0, description="置信度阈值（0.01 ~ 1.0），默认 0.25")
    model_path: Optional[str] = Field(None, description="自定义模型权重相对路径（留空则默认使用系统最佳或默认分割权重）")
    simplify_tolerance: float = Field(0.003, ge=0.0, le=0.05, description="多边形轮廓点简化容差系数，默认 0.003，设为 0 则保留全部原始像素点")


class PromptJsonRequest(BaseModel):
    """Prompt 开放词汇识别 Base64 请求体"""
    image_base64: str = Field(
        ...,
        description="图片 Base64 编码字符串",
        example="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    prompt: str = Field("pig", description="识别提示词（文本词汇），支持多个词用中英文逗号隔开，如 'pig' 或 'pig body, pig head'", example="pig")
    conf: float = Field(0.25, ge=0.01, le=1.0, description="置信度阈值，默认 0.25")
    use_sam: bool = Field(True, description="是否启用 SAM 提取精细多边形轮廓（为 False 则仅返回矩形多边形），默认 True")
    model_path: Optional[str] = Field(None, description="自定义世界模型或 SAM3 模型权重相对路径")
    simplify_tolerance: float = Field(0.003, ge=0.0, le=0.05, description="多边形轮廓点简化容差系数，默认 0.003")


# ==============================================================================
# 图像解码与几何辅助函数
# ==============================================================================

def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """
    将二进制图片字节流在内存中解码为 OpenCV BGR 格式的 numpy ndarray
    避免产生任何磁盘临时文件
    """
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传的图片数据为空")
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="图片格式无法解析，请确保为有效的 JPG/PNG/BMP/WebP 图片")
    return img


def decode_image_base64(b64_str: str) -> np.ndarray:
    """
    解析 Base64 字符串（自动兼容带 Data URI scheme 前缀的情况）并解码为 BGR 图像
    """
    if not b64_str or not b64_str.strip():
        raise HTTPException(status_code=400, detail="Base64 图片数据不能为空")
    
    clean_str = b64_str.strip()
    if "," in clean_str:
        # 兼容例如 "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
        clean_str = clean_str.split(",", 1)[1]
    
    try:
        raw_bytes = base64.b64decode(clean_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Base64 字符串解码失败: {str(e)}")
        
    return decode_image_bytes(raw_bytes)


def simplify_polygon_points(points_list: List[List[float]], tolerance: float = 0.003) -> List[List[float]]:
    """
    基于 OpenCV approxPolyDP 对归一化坐标多边形进行简化，去除冗余噪点
    """
    if tolerance <= 0 or len(points_list) < 4:
        return points_list
    pts = np.array(points_list, dtype=np.float32)
    perimeter = cv2.arcLength(pts, True)
    epsilon = tolerance * perimeter
    approx = cv2.approxPolyDP(pts, epsilon, True)
    simplified = approx.reshape(-1, 2).tolist()
    if len(simplified) >= 3:
        return simplified
    return points_list


def build_prediction_item(
    target_id: int,
    class_id: int,
    class_name: str,
    confidence: float,
    norm_polygon: List[List[float]],
    img_w: int,
    img_h: int
) -> Dict[str, Any]:
    """
    根据归一化多边形顶点，构造包含绝对像素坐标、包围盒、几何质心与像素面积的预测对象
    """
    # 转换为绝对像素坐标
    pixel_polygon = []
    xs = []
    ys = []
    for pt in norm_polygon:
        px = round(float(pt[0] * img_w), 2)
        py = round(float(pt[1] * img_h), 2)
        pixel_polygon.append([px, py])
        xs.append(px)
        ys.append(py)

    # 计算包围盒
    min_x = max(0.0, min(xs)) if xs else 0.0
    min_y = max(0.0, min(ys)) if ys else 0.0
    max_x = min(float(img_w), max(xs)) if xs else 0.0
    max_y = min(float(img_h), max(ys)) if ys else 0.0

    bbox_pixel = [round(min_x, 2), round(min_y, 2), round(max_x, 2), round(max_y, 2)]
    bbox_norm = [
        round(min_x / img_w, 6) if img_w > 0 else 0.0,
        round(min_y / img_h, 6) if img_h > 0 else 0.0,
        round(max_x / img_w, 6) if img_w > 0 else 0.0,
        round(max_y / img_h, 6) if img_h > 0 else 0.0
    ]

    # 计算多边形面积与几何质心 (基于绝对像素坐标)
    area_pixels = 0.0
    centroid = [round((min_x + max_x) / 2.0, 2), round((min_y + max_y) / 2.0, 2)]
    if len(pixel_polygon) >= 3:
        pts_np = np.array(pixel_polygon, dtype=np.float32)
        area_pixels = round(float(cv2.contourArea(pts_np)), 2)
        m = cv2.moments(pts_np)
        if m["m00"] != 0:
            centroid = [round(float(m["m10"] / m["m00"]), 2), round(float(m["m01"] / m["m00"]), 2)]

    return {
        "id": target_id,
        "class_id": class_id,
        "class_name": class_name,
        "confidence": round(float(confidence), 4),
        "box": {
            "xyxy": bbox_pixel,
            "xyxy_normalized": bbox_norm
        },
        "polygon": {
            "points": pixel_polygon,
            "points_normalized": norm_polygon,
            "point_count": len(norm_polygon),
            "area_pixels": area_pixels,
            "centroid": centroid
        }
    }


# ==============================================================================
# 推理执行核心函数
# ==============================================================================

def execute_yolo_seg(
    img: np.ndarray,
    conf: float,
    model_path: Optional[str],
    simplify_tolerance: float
) -> Dict[str, Any]:
    """执行专用 YOLO 分割模型推理"""
    if _predictor is None:
        raise HTTPException(status_code=500, detail="推理引擎尚未就绪，请稍后重试")

    start_time = time.time()
    img_h, img_w = img.shape[:2]

    results = None
    try:
        import torch
        with torch.no_grad():
            model = _predictor.get_yolo_model(model_path)
            # Ultralytics YOLO 支持直接将 OpenCV BGR numpy array 作为输入
            results = model(img, conf=conf, verbose=False)

            predictions = []
            target_counter = 1

            if len(results) > 0:
                r = results[0]
                names = r.names if hasattr(r, "names") else {}

                if r.masks is not None and len(r.masks) > 0:
                    xyn_list = r.masks.xyn
                    cls_list = r.boxes.cls.tolist() if r.boxes is not None and r.boxes.cls is not None else []
                    conf_list = r.boxes.conf.tolist() if r.boxes is not None and r.boxes.conf is not None else []

                    for i, segment in enumerate(xyn_list):
                        if len(segment) >= 3:
                            pts = segment.tolist()
                            if simplify_tolerance > 0:
                                pts = simplify_polygon_points(pts, tolerance=simplify_tolerance)

                            cid = int(cls_list[i]) if i < len(cls_list) else 0
                            cname = names.get(cid, "pig" if cid == 0 else f"class_{cid}")
                            score = float(conf_list[i]) if i < len(conf_list) else 1.0

                            item = build_prediction_item(
                                target_id=target_counter,
                                class_id=cid,
                                class_name=str(cname),
                                confidence=score,
                                norm_polygon=pts,
                                img_w=img_w,
                                img_h=img_h
                            )
                            predictions.append(item)
                            target_counter += 1

            latency_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "image_info": {
                    "width": img_w,
                    "height": img_h,
                    "channels": img.shape[2] if len(img.shape) > 2 else 1
                },
                "count": len(predictions),
                "predictions": predictions,
                "latency_ms": latency_ms
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型分割推理失败: {str(e)}")
    finally:
        if results is not None:
            del results
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def execute_prompt_seg(
    img: np.ndarray,
    prompt_str: str,
    conf: float,
    use_sam: bool,
    model_path: Optional[str],
    simplify_tolerance: float
) -> Dict[str, Any]:
    """执行 Prompt 开放词汇识别推理（YOLO-World 或 SAM 3）"""
    if _predictor is None:
        raise HTTPException(status_code=500, detail="推理引擎尚未就绪，请稍后重试")

    start_time = time.time()
    img_h, img_w = img.shape[:2]

    # 解析提示词
    prompts = [p.strip() for p in prompt_str.replace("，", ",").split(",") if p.strip()]
    if not prompts:
        raise HTTPException(status_code=400, detail="提示词不能为空")

    # 检测是否选用 SAM3
    is_sam3_model = False
    if model_path:
        mp_lower = Path(model_path).name.lower()
        is_sam3_model = mp_lower.startswith("sam3") and mp_lower.endswith(".pt")

    results = None
    sam_results = None

    try:
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        predictions = []
        target_counter = 1

        with torch.no_grad():
            if is_sam3_model:
                # 分支 A: SAM 3 文本语义直推
                sam3_model = _predictor.get_sam3_model(model_path)
                from ultralytics.models.sam import SAM3SemanticPredictor

                overrides = {
                    "conf": conf,
                    "task": "segment",
                    "mode": "predict",
                    "model": model_path,
                    "device": device,
                    "imgsz": 1008,
                    "save": False,
                    "verbose": False
                }
                sam3_predictor = SAM3SemanticPredictor(overrides=overrides)
                results = sam3_predictor(source=img, model=sam3_model, text=prompts)

                if len(results) > 0 and results[0].masks is not None:
                    r = results[0]
                    sam3_masks = r.masks.xyn
                    cls_ids = r.boxes.cls.cpu().numpy().astype(int) if r.boxes is not None and r.boxes.cls is not None else None
                    conf_scores = r.boxes.conf.cpu().numpy() if r.boxes is not None and r.boxes.conf is not None else None

                    for i, segment in enumerate(sam3_masks):
                        if len(segment) >= 3:
                            pts = segment.tolist()
                            if simplify_tolerance > 0:
                                pts = simplify_polygon_points(pts, tolerance=simplify_tolerance)

                            label_name = prompts[0]
                            cls_id = 0
                            if cls_ids is not None and i < len(cls_ids):
                                cls_id = int(cls_ids[i])
                                if cls_id < len(prompts):
                                    label_name = prompts[cls_id]

                            conf_val = float(conf_scores[i]) if conf_scores is not None and i < len(conf_scores) else 1.0

                            item = build_prediction_item(
                                target_id=target_counter,
                                class_id=cls_id,
                                class_name=label_name,
                                confidence=conf_val,
                                norm_polygon=pts,
                                img_w=img_w,
                                img_h=img_h
                            )
                            predictions.append(item)
                            target_counter += 1

                    del r, sam3_predictor
            else:
                # 分支 B: YOLO-World 检测 + SAM 轮廓精细化
                yolo_world = _predictor.get_yolo_world_model(model_path)
                try:
                    yolo_world.set_classes(prompts)
                    if hasattr(yolo_world, 'model') and yolo_world.model is not None:
                        yolo_world.model.to(device)
                    results = yolo_world(img, conf=conf, device=device, verbose=False)
                except Exception as dev_err:
                    if "same device" in str(dev_err) or "cuda" in str(dev_err).lower():
                        del yolo_world
                        if model_path and model_path in _predictor.yolo_world_models:
                            _predictor.yolo_world_models.pop(model_path, None)
                        else:
                            _predictor.yolo_world_models.pop("__default__", None)
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        yolo_world = _predictor.get_yolo_world_model(model_path)
                        yolo_world.set_classes(prompts)
                        if hasattr(yolo_world, 'model') and yolo_world.model is not None:
                            yolo_world.model.to(device)
                        results = yolo_world(img, conf=conf, device=device, verbose=False)
                    else:
                        raise dev_err

                if len(results) > 0 and len(results[0].boxes) > 0:
                    r = results[0]
                    boxes_xyxy = r.boxes.xyxy.cpu().numpy()
                    cls_ids = r.boxes.cls.cpu().numpy().astype(int)
                    conf_scores = r.boxes.conf.cpu().numpy()

                    del r, results
                    results = None

                    sam_success = False
                    if use_sam:
                        try:
                            sam = _predictor.get_sam_model()
                            sam_results = sam(img, bboxes=boxes_xyxy.tolist(), verbose=False)
                            if len(sam_results) > 0 and sam_results[0].masks is not None:
                                sam_masks = sam_results[0].masks.xyn
                                for i, segment in enumerate(sam_masks):
                                    if len(segment) >= 3:
                                        pts = segment.tolist()
                                        if simplify_tolerance > 0:
                                            pts = simplify_polygon_points(pts, tolerance=simplify_tolerance)

                                        c_idx = cls_ids[i] if i < len(cls_ids) else 0
                                        c_label = prompts[c_idx] if c_idx < len(prompts) else prompts[0]
                                        score = float(conf_scores[i]) if i < len(conf_scores) else 1.0

                                        item = build_prediction_item(
                                            target_id=target_counter,
                                            class_id=c_idx,
                                            class_name=c_label,
                                            confidence=score,
                                            norm_polygon=pts,
                                            img_w=img_w,
                                            img_h=img_h
                                        )
                                        predictions.append(item)
                                        target_counter += 1
                                sam_success = True
                        except Exception as sam_e:
                            print(f"[PromptInference] SAM 细化轮廓失败，回退使用矩形包围盒: {sam_e}")
                            sam_success = False
                        finally:
                            if sam_results is not None:
                                del sam_results
                                sam_results = None

                    if not sam_success:
                        # 使用 4 点归一化矩形框作为多边形
                        for i, box in enumerate(boxes_xyxy):
                            x1, y1, x2, y2 = box
                            norm_box = [
                                [round(float(x1 / img_w), 6), round(float(y1 / img_h), 6)],
                                [round(float(x2 / img_w), 6), round(float(y1 / img_h), 6)],
                                [round(float(x2 / img_w), 6), round(float(y2 / img_h), 6)],
                                [round(float(x1 / img_w), 6), round(float(y2 / img_h), 6)]
                            ]
                            c_idx = cls_ids[i] if i < len(cls_ids) else 0
                            c_label = prompts[c_idx] if c_idx < len(prompts) else prompts[0]
                            score = float(conf_scores[i]) if i < len(conf_scores) else 1.0

                            item = build_prediction_item(
                                target_id=target_counter,
                                class_id=c_idx,
                                class_name=c_label,
                                confidence=score,
                                norm_polygon=norm_box,
                                img_w=img_w,
                                img_h=img_h
                            )
                            predictions.append(item)
                            target_counter += 1

        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "image_info": {
                "width": img_w,
                "height": img_h,
                "channels": img.shape[2] if len(img.shape) > 2 else 1
            },
            "count": len(predictions),
            "predictions": predictions,
            "latency_ms": latency_ms
        }
    except Exception as e:
        err_msg = str(e)
        if "clip" in err_msg.lower():
            raise HTTPException(status_code=500, detail="服务器缺少开放词汇文本编码依赖 openai-clip")
        raise HTTPException(status_code=500, detail=f"Prompt 开放词汇识别失败: {err_msg}")
    finally:
        try:
            if results is not None:
                del results
            if sam_results is not None:
                del sam_results
        except Exception:
            pass
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


# ==============================================================================
# 接口路由实现
# ==============================================================================

@router.post(
    "/segment",
    summary="YOLO 模型分割识别 (文件上传方式)",
    description="通过 Multipart Form-Data 直接上传图片文件，调用专用的 YOLO-seg 模型进行实例分割识别，返回目标的轮廓点集、边界框与几何属性。"
)
async def segment_by_upload(
    file: UploadFile = File(..., description="要识别的图片文件 (JPG/PNG/BMP/WebP)"),
    conf: float = Form(0.25, description="置信度阈值 (0.01~1.0)，默认 0.25"),
    model_path: Optional[str] = Form(None, description="自定义模型权重相对路径，留空使用最佳或默认权重"),
    simplify_tolerance: float = Form(0.003, description="多边形轮廓点简化容差系数，默认 0.003")
):
    contents = await file.read()
    img = decode_image_bytes(contents)
    data = execute_yolo_seg(img, conf=conf, model_path=model_path, simplify_tolerance=simplify_tolerance)
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.post(
    "/segment/json",
    summary="YOLO 模型分割识别 (Base64 JSON 方式)",
    description="通过 JSON 传递图片的 Base64 编码字符串，调用专用的 YOLO-seg 模型进行分割识别，返回轮廓点及详细几何数据。"
)
def segment_by_json(req: SegmentJsonRequest):
    img = decode_image_base64(req.image_base64)
    data = execute_yolo_seg(
        img,
        conf=req.conf,
        model_path=req.model_path,
        simplify_tolerance=req.simplify_tolerance
    )
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.post(
    "/prompt",
    summary="Prompt 开放词汇识别 (文件上传方式)",
    description="上传图片并输入提示词（例如 'pig' 或 'pig body, pig head'），利用 YOLO-World / SAM 模型进行零样本目标定位与精准轮廓分割。"
)
async def prompt_by_upload(
    file: UploadFile = File(..., description="要识别的图片文件"),
    prompt: str = Form("pig", description="提示词文本，多个词用逗号分隔，例如 'pig' 或 'pig body'"),
    conf: float = Form(0.25, description="置信度阈值 (0.01~1.0)，默认 0.25"),
    use_sam: bool = Form(True, description="是否启用 SAM 提取精细多边形轮廓，默认 True"),
    model_path: Optional[str] = Form(None, description="自定义世界模型或 SAM3 权重路径"),
    simplify_tolerance: float = Form(0.003, description="轮廓简化容差，默认 0.003")
):
    contents = await file.read()
    img = decode_image_bytes(contents)
    data = execute_prompt_seg(
        img,
        prompt_str=prompt,
        conf=conf,
        use_sam=use_sam,
        model_path=model_path,
        simplify_tolerance=simplify_tolerance
    )
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.post(
    "/prompt/json",
    summary="Prompt 开放词汇识别 (Base64 JSON 方式)",
    description="通过 JSON 传入图片的 Base64 与提示词，调用世界模型进行识别分割。"
)
def prompt_by_json(req: PromptJsonRequest):
    img = decode_image_base64(req.image_base64)
    data = execute_prompt_seg(
        img,
        prompt_str=req.prompt,
        conf=req.conf,
        use_sam=req.use_sam,
        model_path=req.model_path,
        simplify_tolerance=req.simplify_tolerance
    )
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.get(
    "/models",
    summary="查询当前可用推理模型列表",
    description="获取系统当前可用的所有分割模型权重（用于 segment 接口）与世界模型权重（用于 prompt 接口），方便第三方动态指定。"
)
def list_available_models():
    if _workspace_dir is None:
        raise HTTPException(status_code=500, detail="服务目录配置未就绪")

    models_dir = _workspace_dir / "models"
    runs_dir = _workspace_dir / "runs"
    
    segment_models = []
    world_models = []
    seen = set()

    # 1. 扫描训练产物中的分割权重 (runs/**/*.pt)
    if runs_dir.exists():
        for f in runs_dir.rglob("*.pt"):
            fn_l = f.name.lower()
            if "sam" in fn_l or "world" in fn_l:
                continue
            try:
                rel = f.relative_to(_workspace_dir).as_posix()
            except Exception:
                rel = str(f.resolve())
            if rel not in seen:
                seen.add(rel)
                segment_models.append({
                    "name": f.name if f.name != "best.pt" else "best.pt (最佳训练权重)",
                    "path": rel,
                    "type": "trained",
                    "is_best": f.name == "best.pt"
                })

    # 2. 扫描 models/segment
    seg_dir = models_dir / "segment"
    if seg_dir.exists():
        for f in seg_dir.iterdir():
            if f.is_file() and f.suffix.lower() in [".pt", ".onnx", ".engine"]:
                rel = f"models/segment/{f.name}"
                if rel not in seen:
                    seen.add(rel)
                    segment_models.append({
                        "name": f.name,
                        "path": rel,
                        "type": "pretrained",
                        "is_default": f.name == "yolo26s-seg.pt"
                    })

    # 3. 扫描 models/world
    world_dir = models_dir / "world"
    if world_dir.exists():
        for f in world_dir.iterdir():
            if f.is_file() and f.suffix.lower() in [".pt", ".pth", ".onnx"]:
                rel = f"models/world/{f.name}"
                world_models.append({
                    "name": f.name,
                    "path": rel,
                    "type": "world_model"
                })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "segment_models": segment_models,
            "world_models": world_models
        }
    }
