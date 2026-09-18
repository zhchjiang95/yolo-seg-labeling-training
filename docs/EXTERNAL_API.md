# YOLO26s-seg 智能分割平台 —— 第三方开放接口文档 (v1.0)

本文档面向第三方系统开发者（如猪场边缘视觉计算盒、自动估重与体态测算系统、企业级 MES / ERP 平台或移动端应用），提供通过 HTTP API 直接调用平台深度学习模型进行**猪只实例分割、目标定位与轮廓点提取**的完整指南。

---

## 目录
- [1. 接口概述与服务地址](#1-接口概述与服务地址)
- [2. 接口列表汇总](#2-接口列表汇总)
- [3. 详细接口规范](#3-详细接口规范)
  - [3.1 专用分割模型识别 (文件直传)](#31-专用分割模型识别-文件直传)
  - [3.2 专用分割模型识别 (Base64 JSON)](#32-专用分割模型识别-base64-json)
  - [3.3 Prompt 开放词汇识别 (文件直传)](#33-prompt-开放词汇识别-文件直传)
  - [3.4 Prompt 开放词汇识别 (Base64 JSON)](#34-prompt-开放词汇识别-base64-json)
  - [3.5 可用推理模型列表查询](#35-可用推理模型列表查询)
- [4. 返回数据字典与几何特征说明](#4-返回数据字典与几何特征说明)
- [5. 猪只估重与体态分析集成建议](#5-猪只估重与体态分析集成建议)
- [6. 多语言接入代码示例](#6-多语言接入代码示例)
  - [Python 示例](#python-示例)
  - [cURL 命令行示例](#curl-命令行示例)
  - [JavaScript / TypeScript (Fetch) 示例](#javascript--typescript-fetch-示例)
  - [Java (HttpClient) 示例](#java-httpclient-示例)
- [7. 常见问题与显存优化](#7-常见问题与显存优化)

---

## 1. 接口概述与服务地址

- **网络协议**：HTTP / HTTPS
- **数据格式**：支持 `multipart/form-data`（二进制文件直传）与 `application/json`（Base64 传参）两种主流调用模式；统一响应格式为 `application/json`。
- **服务根地址**：`http://<服务器IP>:9523`
- **开放接口前缀**：`/api/v1/inference`
- **在线交互式文档 (Swagger UI)**：`http://<服务器IP>:9523/docs`
- **ReDoc 离线规范文档**：`http://<服务器IP>:9523/redoc`

---

## 2. 接口列表汇总

| 接口名称 | 请求方法 | 路由地址 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **YOLO 分割识别 (文件直传)** | `POST` | `/api/v1/inference/segment` | 边缘计算盒、抓拍相机、Postman / cURL 调试 |
| **YOLO 分割识别 (Base64)** | `POST` | `/api/v1/inference/segment/json` | 微服务 RPC、前端 Canvas 直传、消息队列流水线 |
| **Prompt 开放识别 (文件直传)** | `POST` | `/api/v1/inference/prompt` | 输入提示词（如 `"pig"`、`"pig head"`）零样本识别 |
| **Prompt 开放识别 (Base64)** | `POST` | `/api/v1/inference/prompt/json` | 基于提示词的 JSON 格式开放调用 |
| **查询可用模型列表** | `GET` | `/api/v1/inference/models` | 动态查询可用权重，供调用方指定 `model_path` |

---

## 3. 详细接口规范

### 3.1 专用分割模型识别 (文件直传)
直接上传图片文件，使用系统内训练的最佳权重或默认 `yolo26s-seg.pt` 分割模型，毫秒级快速分割识别目标轮廓。

- **URL**：`POST /api/v1/inference/segment`
- **Content-Type**：`multipart/form-data`

#### 请求参数 (Form Data)
| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :--- | :---: | :--- | :--- |
| `file` | File | 是 | - | 图片文件（支持 JPG, PNG, BMP, WebP 格式） |
| `conf` | Float | 否 | `0.25` | 置信度过滤阈值，取值范围 `0.01 ~ 1.0` |
| `model_path` | String | 否 | `null` | 指定模型权重相对路径。留空则优先使用训练产生的最佳权重 `best.pt`，次选 `models/segment/yolo26s-seg.pt` |
| `simplify_tolerance` | Float | 否 | `0.003` | 多边形轮廓点简化系数（RDP 算法）。设为 `0` 则保留原始逐像素轮廓，适当增大可大幅降低网络传输点数 |

---

### 3.2 专用分割模型识别 (Base64 JSON)
通过 JSON 传递 Base64 编码的图片，无需多段表单封装，便于微服务直接调用。

- **URL**：`POST /api/v1/inference/segment/json`
- **Content-Type**：`application/json`

#### 请求体 (JSON Body)
```json
{
  "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ...",
  "conf": 0.25,
  "model_path": null,
  "simplify_tolerance": 0.003
}
```
> **注**：`image_base64` 字段既支持标准的 Data URI 格式（如 `data:image/jpeg;base64,...`），也支持纯 Base64 字符内容。

---

### 3.3 Prompt 开放词汇识别 (文件直传)
输入自然语言词汇（如 `"pig"`、`"pig body, pig ear"`），利用 YOLO-World 与 SAM 大模型进行开放词汇识别与精准轮廓勾勒。

- **URL**：`POST /api/v1/inference/prompt`
- **Content-Type**：`multipart/form-data`

#### 请求参数 (Form Data)
| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :--- | :---: | :--- | :--- |
| `file` | File | 是 | - | 图片文件 |
| `prompt` | String | 否 | `"pig"` | 提示词文本。支持中英文逗号隔开多个类别，如 `"pig, ear, head"` |
| `conf` | Float | 否 | `0.25` | 置信度阈值 |
| `use_sam` | Boolean| 否 | `true` | 是否启用 SAM 模型进行轮廓精细化。设为 `false` 则仅输出 4 点矩形框 |
| `model_path` | String | 否 | `null` | 可指定具体的世界模型（如 `models/world/yolov8l-worldv2.pt` 或 `sam3.1_multiplex.pt`） |
| `simplify_tolerance` | Float | 否 | `0.003` | 轮廓简化容差 |

---

### 3.4 Prompt 开放词汇识别 (Base64 JSON)
- **URL**：`POST /api/v1/inference/prompt/json`
- **Content-Type**：`application/json`

#### 请求体 (JSON Body)
```json
{
  "image_base64": "/9j/4AAQSkZJRg...",
  "prompt": "pig",
  "conf": 0.25,
  "use_sam": true,
  "model_path": null,
  "simplify_tolerance": 0.003
}
```

---

### 3.5 可用推理模型列表查询
查询当前服务环境下已加载及可供调用的模型列表。

- **URL**：`GET /api/v1/inference/models`

#### 响应示例
```json
{
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
}
```

---

## 4. 返回数据字典与几何特征说明

识别接口统一返回 JSON 格式，如下所示：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "image_info": {
      "width": 1280,
      "height": 720,
      "channels": 3
    },
    "count": 1,
    "predictions": [
      {
        "id": 1,
        "class_id": 0,
        "class_name": "pig",
        "confidence": 0.9426,
        "box": {
          "xyxy": [180.5, 95.2, 940.3, 610.8],
          "xyxy_normalized": [0.141016, 0.132222, 0.734609, 0.848333]
        },
        "polygon": {
          "points": [
            [250.0, 100.5],
            [320.4, 98.2],
            [890.1, 230.6],
            [940.3, 580.0],
            [720.5, 610.8],
            [210.0, 520.4],
            [180.5, 290.1]
          ],
          "points_normalized": [
            [0.195312, 0.139583],
            [0.250312, 0.136389],
            [0.695391, 0.320278],
            [0.734609, 0.805556],
            [0.562891, 0.848333],
            [0.164062, 0.722778],
            [0.141016, 0.402917]
          ],
          "point_count": 7,
          "area_pixels": 268420.5,
          "centroid": [530.2, 385.6]
        }
      }
    ],
    "latency_ms": 35.8
  }
}
```

### 字段含义对照表

| 字段路径 | 类型 | 说明 |
| :--- | :--- | :--- |
| `code` | Integer | HTTP 业务状态码，200 表示处理成功 |
| `message` | String | 状态说明信息 |
| `data.image_info.width` | Integer | 输入图片的实际物理像素宽度 |
| `data.image_info.height` | Integer | 输入图片的实际物理像素高度 |
| `data.count` | Integer | 检测到的有效目标总数 |
| `data.latency_ms` | Float | 模型推理纯计算耗时（单位：毫秒） |
| `predictions[].id` | Integer | 目标在当前图片中的序号索引（从 1 开始） |
| `predictions[].class_id` | Integer | 目标分类数值 ID |
| `predictions[].class_name` | String | 目标分类名称（例如 `"pig"`） |
| `predictions[].confidence` | Float | 识别置信度得分（0.0 ~ 1.0） |
| `predictions[].box.xyxy` | List[Float] | 绝对像素包围盒 `[x_min, y_min, x_max, y_max]` |
| `predictions[].box.xyxy_normalized` | List[Float] | 归一化包围盒 `[0.0 ~ 1.0]`，便于前端自适应适配 |
| `predictions[].polygon.points` | List[[x, y]] | **绝对像素坐标轮廓点集**，每个点为 `[x, y]`，可直接用于 OpenCV 绘制或几何面积换算 |
| `predictions[].polygon.points_normalized` | List[[x, y]] | **归一化轮廓点集**，不受图片缩放影响 |
| `predictions[].polygon.point_count` | Integer | 构成多边形闭合轮廓的顶点总数 |
| `predictions[].polygon.area_pixels` | Float | 猪只轮廓在原图中所占据的像素投影面积（$px^2$） |
| `predictions[].polygon.centroid` | [cx, cy] | 猪只轮廓的二维几何质心像素坐标 |

---

## 5. 猪只估重与体态分析集成建议

本开放接口专为畜牧视觉量测场景设计，返回的几何数据可直接赋能下游业务：
1. **真实面积估算**：
   若已知相机的安装高度与相机内参焦距，设空间分辨率为 $k$ (毫米/像素)，则猪只俯视投影表面积为：
   $$S_{real} = \text{area\_pixels} \times k^2$$
2. **猪只体长与体宽测算**：
   通过拟合 `polygon.points` 的最小外接旋转矩形（`cv2.minAreaRect`），长边对应猪只体长（Length），短边对应猪只体宽（Width）。
3. **结合深度图完成 3D 估重**：
   将 `polygon.points` 或 `polygon.points_normalized` 作为 Mask 掩膜，提取 RGB-D 相机中猪只的点云深度分布，即可精准剔除围栏等背景干扰，计算猪只的体躯体积 $V$ 并推算体重。

---

## 6. 多语言接入代码示例

### Python 示例

#### 方式 1：文件直接上传调用
```python
import requests

url = "http://127.0.0.1:9523/api/v1/inference/segment"
image_path = "sample_pig.jpg"

with open(image_path, "rb") as f:
    files = {"file": ("pig.jpg", f, "image/jpeg")}
    data = {
        "conf": 0.3,
        "simplify_tolerance": 0.003
    }
    response = requests.post(url, files=files, data=data)
    result = response.json()

if result["code"] == 200:
    for pred in result["data"]["predictions"]:
        print(f"目标: {pred['class_name']}, 置信度: {pred['confidence']:.2f}")
        print(f"轮廓点数量: {pred['polygon']['point_count']}")
        print(f"投影像素面积: {pred['polygon']['area_pixels']} px")
```

#### 方式 2：Base64 JSON 格式调用
```python
import requests
import base64

url = "http://127.0.0.1:9523/api/v1/inference/segment/json"

with open("sample_pig.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")

payload = {
    "image_base64": f"data:image/jpeg;base64,{b64}",
    "conf": 0.25,
    "simplify_tolerance": 0.003
}

res = requests.post(url, json=payload).json()
print("检测目标数:", res["data"]["count"])
```

---

### cURL 命令行示例

```bash
# 1. 文件直传识别
curl -X POST "http://127.0.0.1:9523/api/v1/inference/segment" \
     -F "file=@/path/to/pig.jpg" \
     -F "conf=0.25"

# 2. 开放词汇 Prompt 识别
curl -X POST "http://127.0.0.1:9523/api/v1/inference/prompt" \
     -F "file=@/path/to/pig.jpg" \
     -F "prompt=pig" \
     -F "use_sam=true"
```

---

### JavaScript / TypeScript (Fetch) 示例

```javascript
// 文件直传调用
async function detectPig(fileInput) {
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('conf', '0.25');

  const response = await fetch('http://127.0.0.1:9523/api/v1/inference/segment', {
    method: 'POST',
    body: formData
  });

  const res = await response.json();
  if (res.code === 200) {
    console.log('检测到的猪只数量:', res.data.count);
    res.data.predictions.forEach(p => {
      console.log('轮廓坐标点集:', p.polygon.points);
    });
  }
}
```

---

### Java (HttpClient) 示例

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;

public class InferenceDemo {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(Path.of("sample_pig.jpg"));
        String b64 = Base64.getEncoder().encodeToString(bytes);

        String json = "{\"image_base64\":\"" + b64 + "\",\"conf\":0.25}";

        HttpClient client = HttpClient.newHttpClient();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("http://127.0.0.1:9523/api/v1/inference/segment/json"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println("响应内容: " + response.body());
    }
}
```

---

## 7. 常见问题与显存优化

1. **首次调用冷启动说明**：
   首次请求特定模型时，服务端需将模型权重从磁盘加载至 GPU 显存，耗时通常为 1~3 秒；后续相同模型的调用将直接命中内存缓存，平均推理耗时降至几十毫秒。
2. **显存释放与 LRU 机制**：
   服务端内置 LRU 模型调度策略与空闲自动卸载（默认无请求 300 秒后自动释放显存），避免多个模型常驻引发 CUDA OOM。
3. **大图传输优化**：
   如果图片分辨率较高（例如 4K 超高清），建议前端/调用方适当将 `simplify_tolerance` 设置为 `0.003 ~ 0.005`，以显著精简多边形顶点数量，降低网络传输 JSON 体积，而不会损失猪只轮廓的几何特征。
