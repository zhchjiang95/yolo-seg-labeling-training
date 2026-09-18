# -*- coding: utf-8 -*-
"""
第三方系统专用开放推理接口模块 (External Inference API)
提供面向第三方系统的目标分割模型识别与 Prompt 开放词汇识别能力。
支持 Multipart 表单文件直传、图片 URL 地址下载、Base64 编码 JSON 传参三种灵活传图方式。
"""

import time
import base64
import gc
import urllib.request
import urllib.error
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
# 模型检索辅助函数 (与前端下拉列表保持严格一致)
# ==============================================================================

def get_available_segment_models() -> List[Dict[str, Any]]:
    """
    扫描系统内可用的分割模型列表。
    排序规则与前端页面上的模型识别下拉列表严格一致：
    优先按训练最佳权重 best.pt > 最新权重 last.pt > 预置权重 yolo26s-seg.pt > 其他。
    列表首项即为系统默认使用的“最佳模型”。
    """
    if _workspace_dir is None:
        return []

    models_dir = _workspace_dir / "models"
    segment_dir = models_dir / "segment"
    runs_dir = _workspace_dir / "runs"

    models_list = []
    seen_paths = set()

    def is_seg_weight(filename: str) -> bool:
        fn_l = filename.lower()
        if not (fn_l.endswith(".pt") or fn_l.endswith(".onnx") or fn_l.endswith(".engine")):
            return False
        if "sam" in fn_l or "world" in fn_l:
            return False
        return True

    # 1. 递归扫描 runs 目录下的已训练 pt 文件 (优先展示训练权重)
    trained_models = []
    if runs_dir.exists():
        for file in runs_dir.rglob("*.pt"):
            if is_seg_weight(file.name):
                try:
                    rel_path = file.relative_to(_workspace_dir).as_posix()
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
                    "is_best": file.name == "best.pt",
                    "_priority": priority
                })

        trained_models.sort(key=lambda x: x["_priority"])
        for item in trained_models:
            item.pop("_priority", None)
            models_list.append(item)

    # 2. 扫描 models/segment 专有分类子目录下的权重
    if segment_dir.exists():
        for file in segment_dir.iterdir():
            if file.is_file() and is_seg_weight(file.name):
                rel_path = f"models/segment/{file.name}"
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    models_list.append({
                        "name": file.name,
                        "path": rel_path,
                        "type": "default" if file.name == "yolo26s-seg.pt" else "custom",
                        "is_best": len(models_list) == 0
                    })

    # 3. 扫描 models 根目录下的权重 (兼容模式)
    if models_dir.exists():
        for file in models_dir.iterdir():
            if file.is_file() and is_seg_weight(file.name):
                rel_path = f"models/{file.name}"
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    models_list.append({
                        "name": file.name,
                        "path": rel_path,
                        "type": "default" if file.name == "yolo26s-seg.pt" else "custom",
                        "is_best": len(models_list) == 0
                    })

    return models_list


def resolve_sam31_model_path() -> str:
    """
    匹配并锁定系统中的 sam3.1 世界模型（优先使用 sam3.1_multiplex.pt）
    若未检索到任何 sam3.1 权重文件，则返回 None。
    """
    if _workspace_dir is None:
        return None

    models_dir = _workspace_dir / "models"
    world_dir = models_dir / "world"

    candidates = []
    # 1. 优先从 models/world/ 检索
    if world_dir.exists():
        for f in world_dir.iterdir():
            if f.is_file() and "sam3.1" in f.name.lower() and f.suffix.lower() == ".pt":
                candidates.append(f)

    # 2. 其次从 models/ 根目录检索
    if models_dir.exists():
        for f in models_dir.iterdir():
            if f.is_file() and "sam3.1" in f.name.lower() and f.suffix.lower() == ".pt":
                candidates.append(f)

    if not candidates:
        return None

    # 优先匹配 sam3.1_multiplex.pt
    for c in candidates:
        if "multiplex" in c.name.lower():
            try:
                return c.relative_to(_workspace_dir).as_posix()
            except Exception:
                return str(c.resolve())

    # 回退取找到的第一个 sam3.1 权重
    try:
        return candidates[0].relative_to(_workspace_dir).as_posix()
    except Exception:
        return str(candidates[0].resolve())


# ==============================================================================
# Pydantic 请求模型定义
# ==============================================================================

class SegmentJsonRequest(BaseModel):
    """专用分割模型（YOLO-seg）JSON 请求体（支持 Base64 或 URL）"""
    image_base64: Optional[str] = Field(
        None,
        description="图片 Base64 编码字符串（image_base64 与 image_url 至少提供一项）",
        example="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    image_url: Optional[str] = Field(
        None,
        description="图片网络 URL 地址（HTTP/HTTPS），与 image_base64 二选一",
        example="https://example.com/pig.jpg"
    )
    conf: float = Field(0.25, ge=0.01, le=1.0, description="置信度阈值（0.01 ~ 1.0），默认 0.25")
    model_path: Optional[str] = Field(
        None,
        description="模型权重地址，可从 GET /api/v1/inference/models 获取。留空则默认使用系统最好的模型 (如 best.pt)"
    )
    use_sam: bool = Field(
        False,
        description="是否在识别后使用 SAM 进行高保真边缘优化（等同于页面上的【识别并优化】按钮）。false 为单模型全图识别，true 为识别后由 SAM 重分割精修",
        example=False
    )
    simplify_tolerance: float = Field(0.003, ge=0.0, le=0.05, description="多边形轮廓点简化容差系数，默认 0.003，设为 0 则保留全部原始像素点")


class PromptJsonRequest(BaseModel):
    """Prompt 开放词汇识别 JSON 请求体（固定使用 sam3.1 世界模型，支持 Base64 或 URL）"""
    image_base64: Optional[str] = Field(
        None,
        description="图片 Base64 编码字符串（image_base64 与 image_url 至少提供一项）",
        example="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    image_url: Optional[str] = Field(
        None,
        description="图片网络 URL 地址（HTTP/HTTPS），与 image_base64 二选一",
        example="https://example.com/pig.jpg"
    )
    prompt: str = Field("pig", description="识别提示词（文本词汇），支持多个词用中英文逗号隔开，如 'pig' 或 'pig body, pig head'", example="pig")
    conf: float = Field(0.25, ge=0.01, le=1.0, description="置信度阈值，默认 0.25")
    simplify_tolerance: float = Field(0.003, ge=0.0, le=0.05, description="多边形轮廓点简化容差系数，默认 0.003")


# ==============================================================================
# 图像解码与几何辅助函数
# ==============================================================================

def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """二进制字节流解码为 OpenCV BGR 格式的 numpy ndarray"""
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传的图片数据为空")
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="图片格式无法解析，请确保为有效的 JPG/PNG/BMP/WebP 图片")
    return img


def decode_image_base64(b64_str: str) -> np.ndarray:
    """解析 Base64 字符串并解码为 BGR 图像"""
    if not b64_str or not b64_str.strip():
        raise HTTPException(status_code=400, detail="Base64 图片数据不能为空")

    clean_str = b64_str.strip()
    if "," in clean_str:
        clean_str = clean_str.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(clean_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Base64 字符串解码失败: {str(e)}")

    return decode_image_bytes(raw_bytes)


def download_image_from_url(url: str, timeout: int = 15) -> np.ndarray:
    """
    通过 HTTP/HTTPS URL 下载图片并在内存中解码为 OpenCV BGR 格式
    带有网络超时与状态码异常校验
    """
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="图片 URL 不能为空")

    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="图片 URL 格式不合法，必须以 http:// 或 https:// 开头")

    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            if status_code != 200:
                raise HTTPException(status_code=400, detail=f"下载图片失败，服务器返回状态码: {status_code}")
            image_bytes = response.read()
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"从 URL 获取图片失败: HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=400, detail=f"从 URL 获取图片连接失败或超时: {str(e.reason)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"从 URL 获取图片异常: {str(e)}")

    return decode_image_bytes(image_bytes)


def get_image_from_inputs(
    file_bytes: Optional[bytes] = None,
    image_url: Optional[str] = None,
    image_base64: Optional[str] = None
) -> np.ndarray:
    """
    多渠道图像解析器：
    优先级：直接文件字节流 (file_bytes) > 图片网络地址 (image_url) > Base64 编码 (image_base64)
    """
    if file_bytes and len(file_bytes) > 0:
        return decode_image_bytes(file_bytes)
    if image_url and image_url.strip():
        return download_image_from_url(image_url.strip())
    if image_base64 and image_base64.strip():
        return decode_image_base64(image_base64.strip())

    raise HTTPException(
        status_code=400,
        detail="未提供任何有效的图片输入。请上传图片文件 (file)、提供图片下载地址 (image_url) 或传入 Base64 编码 (image_base64)"
    )


def simplify_polygon_points(points_list: List[List[float]], tolerance: float = 0.003) -> List[List[float]]:
    """基于 OpenCV approxPolyDP 对多边形点进行几何简化"""
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
    """构造包含绝对像素坐标、包围盒、几何质心与像素面积的预测对象"""
    pixel_polygon = []
    xs = []
    ys = []
    for pt in norm_polygon:
        px = round(float(pt[0] * img_w), 2)
        py = round(float(pt[1] * img_h), 2)
        pixel_polygon.append([px, py])
        xs.append(px)
        ys.append(py)

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
    use_sam: bool,
    simplify_tolerance: float
) -> Dict[str, Any]:
    """
    执行专用 YOLO 分割模型推理。
    支持两种模式：
    1. use_sam=False: 全图单分割模型快速推理；
    2. use_sam=True: 识别后紧接着使用 SAM 模型进行全图高保真边缘重分割优化（等同于页面【✨ 识别并优化】按钮）。
    如果未传入 model_path，自动选用可用模型列表中的第 1 个（最佳权重）。
    """
    if _predictor is None:
        raise HTTPException(status_code=500, detail="推理引擎尚未就绪，请稍后重试")

    # 1. 确定最终使用的模型路径
    actual_model_path = model_path
    if not actual_model_path or not actual_model_path.strip():
        available = get_available_segment_models()
        if available:
            actual_model_path = available[0]["path"]
            print(f"[YOLO-seg] 未指定 model_path，默认选用系统最佳权重: {actual_model_path}")
        else:
            actual_model_path = None

    start_time = time.time()
    img_h, img_w = img.shape[:2]

    results = None
    sam_results = None

    try:
        import torch
        with torch.no_grad():
            # 步骤 A: 调用选定的 YOLO 分割模型
            model = _predictor.get_yolo_model(actual_model_path)
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

                    # 提取初步多边形列表与外接矩形框
                    initial_targets = []
                    boxes_for_sam = []

                    for i, segment in enumerate(xyn_list):
                        if len(segment) >= 3:
                            pts = segment.tolist()
                            cid = int(cls_list[i]) if i < len(cls_list) else 0
                            cname = names.get(cid, "pig" if cid == 0 else f"class_{cid}")
                            score = float(conf_list[i]) if i < len(conf_list) else 1.0

                            # 计算带 padding 的外接框，供 SAM 优化使用
                            xs = [p[0] for p in pts]
                            ys = [p[1] for p in pts]
                            min_x, max_x = min(xs), max(xs)
                            min_y, max_y = min(ys), max(ys)
                            w_box = max(max_x - min_x, 1e-4)
                            h_box = max(max_y - min_y, 1e-4)
                            pad_x = w_box * 0.03
                            pad_y = h_box * 0.03

                            bx1 = max(0.0, min_x - pad_x) * img_w
                            by1 = max(0.0, min_y - pad_y) * img_h
                            bx2 = min(1.0, max_x + pad_x) * img_w
                            by2 = min(1.0, max_y + pad_y) * img_h

                            boxes_for_sam.append([bx1, by1, bx2, by2])
                            initial_targets.append({
                                "class_id": cid,
                                "class_name": str(cname),
                                "confidence": score,
                                "points": pts
                            })

                    # 步骤 B: 若开启 use_sam=True，调用 SAM 批量进行边缘重分割优化
                    sam_refined_success = False
                    if use_sam and boxes_for_sam:
                        try:
                            sam = _predictor.get_sam_model()
                            sam_results = sam(img, bboxes=boxes_for_sam, verbose=False)
                            if len(sam_results) > 0 and sam_results[0].masks is not None:
                                sam_masks = sam_results[0].masks.xyn
                                for s_idx, s_segment in enumerate(sam_masks):
                                    if s_idx < len(initial_targets) and len(s_segment) >= 3:
                                        initial_targets[s_idx]["points"] = s_segment.tolist()
                                sam_refined_success = True
                        except Exception as sam_err:
                            print(f"[YOLO-seg] SAM 边缘优化失败，自动回退使用 YOLO 原生轮廓: {sam_err}")
                            sam_refined_success = False
                        finally:
                            if sam_results is not None:
                                del sam_results
                                sam_results = None

                    # 步骤 C: 构建最终输出对象
                    for target in initial_targets:
                        pts = target["points"]
                        if simplify_tolerance > 0:
                            pts = simplify_polygon_points(pts, tolerance=simplify_tolerance)

                        item = build_prediction_item(
                            target_id=target_counter,
                            class_id=target["class_id"],
                            class_name=target["class_name"],
                            confidence=target["confidence"],
                            norm_polygon=pts,
                            img_w=img_w,
                            img_h=img_h
                        )
                        predictions.append(item)
                        target_counter += 1

            latency_ms = round((time.time() - start_time) * 1000, 2)
            mode_desc = "segment_with_sam" if (use_sam and len(predictions) > 0) else "segment_only"

            return {
                "image_info": {
                    "width": img_w,
                    "height": img_h,
                    "channels": img.shape[2] if len(img.shape) > 2 else 1
                },
                "model_used": actual_model_path,
                "mode": mode_desc,
                "count": len(predictions),
                "predictions": predictions,
                "latency_ms": latency_ms
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型分割推理失败: {str(e)}")
    finally:
        if results is not None:
            del results
        if sam_results is not None:
            del sam_results
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
    simplify_tolerance: float
) -> Dict[str, Any]:
    """
    执行 Prompt 开放词汇识别推理。
    按照要求固定使用世界模型 sam3.1_multiplex.pt（若系统中未匹配到 sam3.1 系列权重则直接报错返回）。
    """
    if _predictor is None:
        raise HTTPException(status_code=500, detail="推理引擎尚未就绪，请稍后重试")

    # 1. 匹配并锁定 sam3.1 世界模型
    sam31_model_path = resolve_sam31_model_path()
    if not sam31_model_path:
        raise HTTPException(
            status_code=400,
            detail="系统未检索到 sam3.1 世界模型权重 (如 models/world/sam3.1_multiplex.pt)，开放词汇识别不可用。请确认权重文件已正确放置在 models/world/ 目录下。"
        )

    start_time = time.time()
    img_h, img_w = img.shape[:2]

    # 解析提示词
    prompts = [p.strip() for p in prompt_str.replace("，", ",").split(",") if p.strip()]
    if not prompts:
        raise HTTPException(status_code=400, detail="提示词不能为空")

    results = None
    try:
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        predictions = []
        target_counter = 1

        with torch.no_grad():
            sam3_model = _predictor.get_sam3_model(sam31_model_path)
            from ultralytics.models.sam import SAM3SemanticPredictor

            overrides = {
                "conf": conf,
                "task": "segment",
                "mode": "predict",
                "model": sam31_model_path,
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

        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "image_info": {
                "width": img_w,
                "height": img_h,
                "channels": img.shape[2] if len(img.shape) > 2 else 1
            },
            "model_used": sam31_model_path,
            "count": len(predictions),
            "predictions": predictions,
            "latency_ms": latency_ms
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt 开放词汇识别失败: {str(e)}")
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


# ==============================================================================
# 接口路由实现
# ==============================================================================

@router.post(
    "/segment",
    summary="YOLO 专用分割识别 (文件上传 / 图片URL 表单方式)",
    description="支持通过 Multipart 表单直接上传图片文件或提供图片 HTTP/HTTPS URL 地址。支持全图单分割模型推理与识别后使用 SAM 边缘优化两种形式。默认选用系统最佳模型。"
)
async def segment_by_upload(
    file: Optional[UploadFile] = File(None, description="要识别的图片文件 (JPG/PNG/BMP/WebP，与 image_url 二选一)"),
    image_url: Optional[str] = Form(None, description="图片网络 URL 地址（HTTP/HTTPS，与 file 二选一）"),
    conf: float = Form(0.25, description="置信度阈值 (0.01~1.0)，默认 0.25"),
    model_path: Optional[str] = Form(None, description="自定义模型权重相对路径，留空默认使用系统最佳模型 (如 best.pt)"),
    use_sam: bool = Form(False, description="是否在识别后使用 SAM 进行高保真边缘优化（等同于页面【识别并优化】按钮），默认 False 为全图单模型识别"),
    simplify_tolerance: float = Form(0.003, description="多边形轮廓点简化容差系数，默认 0.003")
):
    file_bytes = await file.read() if file else None
    img = get_image_from_inputs(file_bytes=file_bytes, image_url=image_url)
    data = execute_yolo_seg(
        img,
        conf=conf,
        model_path=model_path,
        use_sam=use_sam,
        simplify_tolerance=simplify_tolerance
    )
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.post(
    "/segment/json",
    summary="YOLO 专用分割识别 (Base64 / 图片URL JSON 方式)",
    description="通过 JSON 传递图片 Base64 或图片网络 URL 地址，支持全图单模型推理与识别后使用 SAM 边缘优化两种形式。默认选用最佳模型。"
)
def segment_by_json(req: SegmentJsonRequest):
    img = get_image_from_inputs(
        image_url=req.image_url,
        image_base64=req.image_base64
    )
    data = execute_yolo_seg(
        img,
        conf=req.conf,
        model_path=req.model_path,
        use_sam=req.use_sam,
        simplify_tolerance=req.simplify_tolerance
    )
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.post(
    "/prompt",
    summary="Prompt 开放词汇识别 (文件上传 / 图片URL 表单方式)",
    description="支持上传图片文件或提供图片 URL，固定使用系统世界模型 sam3.1_multiplex.pt 进行开放词汇零样本识别与精细轮廓提取。"
)
async def prompt_by_upload(
    file: Optional[UploadFile] = File(None, description="要识别的图片文件 (与 image_url 二选一)"),
    image_url: Optional[str] = Form(None, description="图片网络 URL 地址 (与 file 二选一)"),
    prompt: str = Form("pig", description="提示词文本，多个词用逗号分隔，例如 'pig' 或 'pig body'"),
    conf: float = Form(0.25, description="置信度阈值 (0.01~1.0)，默认 0.25"),
    simplify_tolerance: float = Form(0.003, description="轮廓简化容差，默认 0.003")
):
    file_bytes = await file.read() if file else None
    img = get_image_from_inputs(file_bytes=file_bytes, image_url=image_url)
    data = execute_prompt_seg(
        img,
        prompt_str=prompt,
        conf=conf,
        simplify_tolerance=simplify_tolerance
    )
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.post(
    "/prompt/json",
    summary="Prompt 开放词汇识别 (Base64 / 图片URL JSON 方式)",
    description="通过 JSON 传递图片 Base64 或图片网络 URL 地址，固定使用系统世界模型 sam3.1_multiplex.pt 进行开放词汇识别分割。"
)
def prompt_by_json(req: PromptJsonRequest):
    img = get_image_from_inputs(
        image_url=req.image_url,
        image_base64=req.image_base64
    )
    data = execute_prompt_seg(
        img,
        prompt_str=req.prompt,
        conf=req.conf,
        simplify_tolerance=req.simplify_tolerance
    )
    return {
        "code": 200,
        "message": "success",
        "data": data
    }


@router.get(
    "/models",
    summary="查询当前可用分割模型列表 (与页面下拉列表严格一致)",
    description="获取当前页面上模型识别下拉列表中的所有分割模型，列表第 1 项为系统默认使用的最佳权重。"
)
def list_available_models():
    models_list = get_available_segment_models()
    sam31_model = resolve_sam31_model_path()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "default_best_model": models_list[0] if models_list else None,
            "models": models_list,
            "sam31_world_model": sam31_model
        }
    }
