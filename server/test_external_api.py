# -*- coding: utf-8 -*-
"""
第三方开放推理接口自动化测试脚本 (包含 image_url 测试)
"""

import sys
import os
import io
import json
import base64
import threading
import http.server
import socketserver
import numpy as np
import cv2
from pathlib import Path

# 确保导入 server 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def create_sample_image_bytes():
    """生成一张 320x240 的模拟彩色图片二进制字节流"""
    img = np.full((240, 320, 3), 220, dtype=np.uint8)
    cv2.ellipse(img, (160, 120), (80, 50), 0, 0, 360, (50, 120, 200), -1)
    success, encoded = cv2.imencode(".jpg", img)
    if not success:
        raise RuntimeError("图片编码失败")
    return encoded.tobytes()

class MockImageHandler(http.server.SimpleHTTPRequestHandler):
    """用于测试 image_url 的微型本地 HTTP 图片服务器"""
    img_bytes = create_sample_image_bytes()
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(self.img_bytes)))
        self.end_headers()
        self.wfile.write(self.img_bytes)

    def log_message(self, format, *args):
        pass

def start_mock_http_server():
    server = socketserver.TCPServer(("127.0.0.1", 0), MockImageHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/sample.jpg"

def test_models_api():
    print(">>> 1. 测试 GET /api/v1/inference/models")
    res = client.get("/api/v1/inference/models")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 200
    print(f"    [通过] 检索到分割模型 {len(body['data']['models'])} 个")

def test_url_input_api(mock_url):
    print(f">>> 2. 测试 POST /api/v1/inference/segment/json (通过图片网络 URL: {mock_url})")
    payload = {
        "image_url": mock_url,
        "conf": 0.25,
        "use_sam": False
    }
    res = client.post("/api/v1/inference/segment/json", json=payload)
    assert res.status_code == 200, f"调用失败: {res.text}"
    body = res.json()
    assert body["code"] == 200
    assert "predictions" in body["data"]
    print(f"    [通过] URL 图片下载并推理成功，耗时: {body['data']['latency_ms']}ms, 采用模型: {body['data']['model_used']}")

    print(">>> 3. 测试表单方式传 image_url")
    data = {
        "image_url": mock_url,
        "conf": "0.25",
        "use_sam": "false"
    }
    res_form = client.post("/api/v1/inference/segment", data=data)
    assert res_form.status_code == 200, f"调用失败: {res_form.text}"
    body_form = res_form.json()
    assert body_form["code"] == 200
    print(f"    [通过] 表单 image_url 传参成功，模式: {body_form['data']['mode']}")

if __name__ == "__main__":
    print("=== 开始运行第三方开放接口测试 (含 URL 传参验证) ===")
    mock_server, mock_url = start_mock_http_server()
    try:
        test_models_api()
        test_url_input_api(mock_url)
        print("=== 所有 URL 传参测试均已顺利通过！ ===")
    finally:
        mock_server.shutdown()
