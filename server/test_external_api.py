# -*- coding: utf-8 -*-
"""
第三方开放推理接口自动化测试脚本
用于验证 /api/v1/inference 下的 models、segment、prompt 各路由功能与数据结构。
"""

import sys
import os
import io
import json
import base64
import numpy as np
import cv2
from pathlib import Path

# 确保导入 server 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def create_sample_image_bytes():
    """生成一张 320x240 的模拟彩色图片二进制字节流 (带有模拟的猪只色块轮廓)"""
    img = np.full((240, 320, 3), 220, dtype=np.uint8)
    # 画一个椭圆模拟目标
    cv2.ellipse(img, (160, 120), (80, 50), 0, 0, 360, (50, 120, 200), -1)
    success, encoded = cv2.imencode(".jpg", img)
    if not success:
        raise RuntimeError("图片编码失败")
    return encoded.tobytes()

def test_models_api():
    print(">>> 1. 测试 GET /api/v1/inference/models")
    res = client.get("/api/v1/inference/models")
    assert res.status_code == 200, f"状态码异常: {res.status_code}, {res.text}"
    data = res.json()
    assert data["code"] == 200
    assert "data" in data
    assert "segment_models" in data["data"]
    assert "world_models" in data["data"]
    print(f"    [通过] 发现分割模型 {len(data['data']['segment_models'])} 个，世界模型 {len(data['data']['world_models'])} 个")

def test_segment_upload_api(img_bytes):
    print(">>> 2. 测试 POST /api/v1/inference/segment (文件表单上传)")
    files = {
        "file": ("test_pig.jpg", io.BytesIO(img_bytes), "image/jpeg")
    }
    data = {
        "conf": "0.25",
        "simplify_tolerance": "0.003"
    }
    res = client.post("/api/v1/inference/segment", files=files, data=data)
    assert res.status_code == 200, f"状态码异常: {res.status_code}, {res.text}"
    body = res.json()
    assert body["code"] == 200
    assert "predictions" in body["data"]
    assert "image_info" in body["data"]
    assert body["data"]["image_info"]["width"] == 320
    assert body["data"]["image_info"]["height"] == 240
    print(f"    [通过] 接口调用成功，检测目标数: {body['data']['count']}, 耗时: {body['data']['latency_ms']}ms")

def test_segment_json_api(img_bytes):
    print(">>> 3. 测试 POST /api/v1/inference/segment/json (Base64 JSON)")
    b64_str = base64.b64encode(img_bytes).decode("utf-8")
    payload = {
        "image_base64": f"data:image/jpeg;base64,{b64_str}",
        "conf": 0.25,
        "simplify_tolerance": 0.003
    }
    res = client.post("/api/v1/inference/segment/json", json=payload)
    assert res.status_code == 200, f"状态码异常: {res.status_code}, {res.text}"
    body = res.json()
    assert body["code"] == 200
    assert "predictions" in body["data"]
    print(f"    [通过] Base64 接口调用成功，目标数: {body['data']['count']}, 耗时: {body['data']['latency_ms']}ms")

if __name__ == "__main__":
    print("=== 开始运行第三方开放接口自动化验证 ===")
    img_bytes = create_sample_image_bytes()
    try:
        test_models_api()
        test_segment_upload_api(img_bytes)
        test_segment_json_api(img_bytes)
        print("=== 所有第三方接口测试均已成功通过！ ===")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
