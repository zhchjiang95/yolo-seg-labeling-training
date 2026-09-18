# YOLO26s-seg 智能分割平台 —— 第三方开放接口文档 (v1.1)

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
  - [3.5 可用推理模型列表查询 (与页面下拉严格一致)](#35-可用推理模型列表查询-与页面下拉严格一致)
- [4. 返回数据字典与几何特征说明](#4-返回数据字典与几何特征说明)
- [5. 猪只估重与体态分析集成建议](#5-猪只估重与体态分析集成建议)
- [6. 多语言接入代码示例](#6-多语言接入代码示例)
  - [Python 示例 (单模型识别 vs 识别并优化)](#python-示例-单模型识别-vs-识别并优化)
  - [cURL 命令行示例](#curl-命令行示例)
  - [JavaScript / TypeScript 示例](#javascript--typescript-示例)
  - [Java (HttpClient) 示例](#java-httpclient-示例)
- [7. 常见问题与显存优化](#7-常见问题与显存优化)

---

## 1. 接口概述与服务地址

- **网络协议**：HTTP / HTTPS
- **数据格式**：支持 `multipart/form-data`（二进制文件直传）与 `application/json`（Base64 传参）两种调用模式；统一响应格式为 `application/json`。
- **服务根地址**：`http://<服务器IP>:9523`
- **开放接口前缀**：`/api/v1/inference`
- **在线交互式文档 (Swagger UI)**：`http://<服务器IP>:9523/docs`
- **ReDoc 离线规范文档**：`http://<服务器IP>:9523/redoc`

---

## 2. 接口列表汇总

| 接口名称 | 请求方法 | 路由地址 | 核心特性说明 |
| :--- | :--- | :--- | :--- |
| **YOLO 分割识别 (文件直传)** | `POST` | `/api/v1/inference/segment` | 支持**单分割模型推理**与**识别后SAM优化**两种形式；可传 `model_path`，默认使用最佳模型 |
| **YOLO 分割识别 (Base64)** | `POST` | `/api/v1/inference/segment/json` | Base64 编码格式调用，功能同上 |
| **Prompt 开放识别 (文件直传)** | `POST` | `/api/v1/inference/prompt` | **固定使用世界模型 `sam3.1_multiplex.pt`**，输入自然语言词汇（如 `"pig"`）直推高保真轮廓 |
| **Prompt 开放识别 (Base64)** | `POST` | `/api/v1/inference/prompt/json` | Base64 格式开放词汇调用，固定使用 `sam3.1` |
| **查询可用模型列表** | `GET` | `/api/v1/inference/models` | **与页面上模型识别下拉列表严格一致**，首项即为系统默认最佳模型 |

---

## 3. 详细接口规范

### 3.1 专用分割模型识别 (文件直传 / 表单传参)
直接上传图片文件或传递图片网络 URL 进行目标分割识别。与 Web 页面上的模型识别能力完全一致，支持两种形式：
1. **全图单分割模型快速识别 (`use_sam=false`)**：直接输出 YOLO-seg 原生提取的目标实例轮廓，速度极快（几十毫秒）；
2. **识别后使用 SAM 高保真优化 (`use_sam=true`)**：等同于页面上的【✨ 识别并优化】按钮，YOLO 模型定位目标后自动由 SAM 模型进行边缘重分割，边缘极致贴合。

- **URL**：`POST /api/v1/inference/segment`
- **Content-Type**：`multipart/form-data`

#### 请求参数 (Form Data)
| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :--- | :---: | :--- | :--- |
| `file` | File | 二选一 | - | 图片文件（支持 JPG, PNG, BMP, WebP 格式，与 `image_url` 二选一） |
| `image_url` | String | 二选一 | `null` | **图片的 HTTP/HTTPS 网络地址**（如 `https://example.com/pig.jpg`，服务端自动拉取解码） |
| `conf` | Float | 否 | `0.25` | 置信度过滤阈值，取值范围 `0.01 ~ 1.0` |
| `model_path` | String | 否 | `null` | 模型权重地址，可通过 `GET /api/v1/inference/models` 获取。**留空则默认使用系统最佳模型（如 `best.pt`）** |
| `use_sam` | Boolean| 否 | `false` | **是否在识别后使用 SAM 进行高保真边缘优化**：<br>• `false`：全图单分割模型推理（速度最快）<br>• `true`：识别后调用 SAM 重分割精修（等同于页面【识别并优化】） |
| `simplify_tolerance` | Float | 否 | `0.003` | 多边形轮廓点简化系数（RDP 算法）。设为 `0` 则保留原始逐像素轮廓 |

---

### 3.2 专用分割模型识别 (URL / Base64 JSON)
通过 JSON 请求体传递图片的网络 URL 或 Base64 编码字符串。

- **URL**：`POST /api/v1/inference/segment/json`
- **Content-Type**：`application/json`

#### 请求体示例 1 (推荐：直接传入图片网络 URL)
```json
{
  "image_url": "https://your-domain.com/images/pig_sample.jpg",
  "conf": 0.25,
  "model_path": null,
  "use_sam": false,
  "simplify_tolerance": 0.003
}
```

#### 请求体示例 2 (传入图片 Base64)
```json
{
  "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "conf": 0.25,
  "use_sam": true
}
```

---

### 3.3 Prompt 开放词汇识别 (文件上传 / 图片 URL)
输入自然语言词汇（例如 `"pig"` 或 `"pig body, pig head"`），通过大模型进行开放词汇零样本识别。
> 📌 **注意**：本接口**固定使用世界模型 `sam3.1_multiplex.pt`**，外部调用方无需也无法修改模型路径。服务端会自动在 `models/world/` 目录下匹配 `sam3.1` 权重。若系统未检索到该权重，接口将直接报错返回提示。

- **URL**：`POST /api/v1/inference/prompt`
- **Content-Type**：`multipart/form-data`

#### 请求参数 (Form Data)
| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :--- | :---: | :--- | :--- |
| `file` | File | 二选一 | - | 图片文件（与 `image_url` 二选一） |
| `image_url` | String | 二选一 | `null` | **图片的 HTTP/HTTPS 网络地址**（与 `file` 二选一） |
| `prompt` | String | 否 | `"pig"` | 提示词文本，支持多个类别用中英文逗号隔开 |
| `conf` | Float | 否 | `0.25` | 置信度阈值 |
| `simplify_tolerance` | Float | 否 | `0.003` | 轮廓简化容差 |

---

### 3.4 Prompt 开放词汇识别 (URL / Base64 JSON)
- **URL**：`POST /api/v1/inference/prompt/json`
- **Content-Type**：`application/json`

#### 请求体 (JSON Body)
```json
{
  "image_url": "https://your-domain.com/images/pig_sample.jpg",
  "prompt": "pig",
  "conf": 0.25,
  "simplify_tolerance": 0.003
}
```
*(也可以使用 `"image_base64": "/9j/4AAQSk..."` 传递)*

---

### 3.5 可用推理模型列表查询 (与页面下拉严格一致)
查询当前系统中可用的分割模型列表。**返回的列表与 Web 标注页面上【模型识别】下拉框列表完全一致**。

- **URL**：`GET /api/v1/inference/models`

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "default_best_model": {
      "name": "best.pt (最佳权重)",
      "path": "runs/segment/yolo26s_train/weights/best.pt",
      "type": "trained",
      "is_best": true
    },
    "models": [
      {
        "name": "best.pt (最佳权重)",
        "path": "runs/segment/yolo26s_train/weights/best.pt",
        "type": "trained",
        "is_best": true
      },
      {
        "name": "yolo26s-seg.pt",
        "path": "models/segment/yolo26s-seg.pt",
        "type": "default",
        "is_best": false
      }
    ],
    "sam31_world_model": "models/world/sam3.1_multiplex.pt"
  }
}
```
> **说明**：
> - `data.default_best_model` 即为调用分割接口不传 `model_path` 时，默认自动选用的系统最佳模型；
> - `data.models` 数组包含所有可选模型的 `name` 和 `path`；
> - `data.sam31_world_model` 展示了开放词汇识别所绑定的 `sam3.1` 权重文件路径。

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
    "model_used": "runs/segment/yolo26s_train/weights/best.pt",
    "mode": "segment_with_sam",
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
    "latency_ms": 115.8
  }
}
```

### 字段含义对照表

| 字段路径 | 类型 | 说明 |
| :--- | :--- | :--- |
| `code` | Integer | HTTP 业务状态码，200 表示成功 |
| `data.model_used` | String | **本次推理实际采用的模型权重相对路径** |
| `data.mode` | String | **推理执行模式**：`segment_only`（单模型全图识别）或 `segment_with_sam`（识别并使用 SAM 优化） |
| `data.image_info` | Object | 图片实际尺寸 `width`, `height`, `channels` |
| `data.count` | Integer | 识别到的有效目标总数 |
| `data.latency_ms` | Float | 模型推理耗时（毫秒） |
| `predictions[].id` | Integer | 目标索引（从 1 开始） |
| `predictions[].class_id` | Integer | 类别 ID |
| `predictions[].class_name` | String | 类别名称（如 `"pig"`） |
| `predictions[].confidence` | Float | 置信度得分（0.0 ~ 1.0） |
| `predictions[].box.xyxy` | List[Float] | 绝对像素包围盒 `[x1, y1, x2, y2]` |
| `predictions[].box.xyxy_normalized`| List[Float] | 归一化包围盒 `[0.0 ~ 1.0]` |
| `predictions[].polygon.points` | List[[x, y]] | **绝对像素坐标轮廓点集**，可直接用于 OpenCV 绘制或几何面积换算 |
| `predictions[].polygon.points_normalized`| List[[x, y]] | **归一化轮廓点集**，不受图片物理缩放影响 |
| `predictions[].polygon.point_count` | Integer | 闭合轮廓的顶点总数 |
| `predictions[].polygon.area_pixels` | Float | 猪只在原图中的像素投影面积（$px^2$） |
| `predictions[].polygon.centroid` | [cx, cy] | 猪只轮廓的几何质心坐标 |

---

## 5. 猪只估重与体态分析集成建议

1. **投影表面积换算**：若已知相机空间分辨率为 $k$ (毫米/像素)，则猪只俯视投影真实面积为 $S_{real} = \text{area\_pixels} \times k^2$。
2. **体长与体宽**：通过拟合 `polygon.points` 的最小外接旋转矩形（`cv2.minAreaRect`），长边即为体长，短边即为体宽。
3. **结合 SAM 优化 (`use_sam=true`)**：在背膘与体型轮廓精细测算场景，建议开启 `use_sam=true`，能将背部边缘贴合度提升至亚像素级别。

---

## 6. 多语言接入代码示例

### Python 示例 (单模型识别 vs 识别并优化)

```python
import requests

url = "http://127.0.0.1:9523/api/v1/inference/segment"

# 1. 模式一：单模型极速识别 (默认使用最佳模型)
with open("pig.jpg", "rb") as f:
    res = requests.post(url, files={"file": f}, data={"conf": 0.25, "use_sam": "false"}).json()
print("单模型推理完成，耗时:", res["data"]["latency_ms"], "ms，使用模型:", res["data"]["model_used"])

# 2. 模式二：识别并使用 SAM 进行高保真边缘优化
with open("pig.jpg", "rb") as f:
    res_refined = requests.post(url, files={"file": f}, data={"conf": 0.25, "use_sam": "true"}).json()
print("识别并优化完成，模式:", res_refined["data"]["mode"])
for p in res_refined["data"]["predictions"]:
    print(f"猪只轮廓点数: {p['polygon']['point_count']}, 投影面积: {p['polygon']['area_pixels']} px^2")
```

---

### cURL 命令行示例

```bash
# 1. 查询可用模型列表（与页面下拉一致）
curl -X GET "http://127.0.0.1:9523/api/v1/inference/models"

# 2. 单模型全图识别 (默认最佳权重)
curl -X POST "http://127.0.0.1:9523/api/v1/inference/segment" \
     -F "file=@pig.jpg" \
     -F "use_sam=false"

# 3. 识别并使用 SAM 高保真优化
curl -X POST "http://127.0.0.1:9523/api/v1/inference/segment" \
     -F "file=@pig.jpg" \
     -F "use_sam=true"

# 4. Prompt 开放识别 (固定使用 sam3.1)
curl -X POST "http://127.0.0.1:9523/api/v1/inference/prompt" \
     -F "file=@pig.jpg" \
     -F "prompt=pig"
```

---

### JavaScript / TypeScript 示例

```javascript
// 识别并使用 SAM 优化调用
async function detectAndRefinePig(fileInput) {
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('use_sam', 'true'); // 开启 SAM 优化
  formData.append('conf', '0.25');

  const res = await fetch('http://127.0.0.1:9523/api/v1/inference/segment', {
    method: 'POST',
    body: formData
  }).then(r => r.json());

  if (res.code === 200) {
    console.log(`检测到 ${res.data.count} 头猪只，模式: ${res.data.mode}`);
    res.data.predictions.forEach(p => {
      console.log('绝对像素轮廓:', p.polygon.points);
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

public class ClientDemo {
    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(Path.of("pig.jpg"));
        String b64 = Base64.getEncoder().encodeToString(bytes);

        // use_sam=true: 识别并使用 SAM 优化
        String json = "{\"image_base64\":\"" + b64 + "\",\"conf\":0.25,\"use_sam\":true}";

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

1. **`use_sam` 开关如何选择？**
   - 如果系统追求极低延迟（如视频流每秒多帧检测、相机实时抓拍计数），建议使用 `use_sam=false`（纯 YOLO 推理，耗时约 20~50ms）；
   - 如果系统用于高精度体重估算、体躯尺寸精细测算，建议开启 `use_sam=true`（耗时约 100~200ms），边缘精度达到最高。
2. **开放词汇固定 sam3.1 失败提示**：
   - 若返回 `系统未检索到 sam3.1 世界模型权重`，请确认已将官方 `sam3.1_multiplex.pt` 放置在项目的 `models/world/` 目录下。
