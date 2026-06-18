# -*- coding: utf-8 -*-
import os
import sys
import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional

# 正则表达式定义，用于解析训练日志
# 匹配类似 "  1/300      2.34G     0.8752      1.124     0.7634     0.9845         12        960:"
EPOCH_PROGRESS_PATTERN = re.compile(r'^\s*(\d+)/(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+):')
# 匹配 "all        103        103      0.823      0.791      0.812      0.543" 这样的指标行
# 分割模型可能有 Box 和 Seg 两组指标，这里我们通用捕获
METRIC_LINE_PATTERN = re.compile(r'^\s*all\s+\d+\s+\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+))?')

class YOLOTrainer:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.log_file = self.workspace_dir / "server" / "train.log"
        self.config_file = self.workspace_dir / "server" / "temp_config.json"
        self.runner_file = self.workspace_dir / "server" / "temp_run.py"
        
        # 训练状态变量
        self.state = "idle"  # idle, preparing, training, completed, failed, stopped
        self.process: Optional[subprocess.Popen] = None
        self.progress = {
            "epoch": 0,
            "total_epochs": 0,
            "percent": 0,
            "eta": "--:--:--",
            "box_loss": 0.0,
            "seg_loss": 0.0,
            "cls_loss": 0.0,
            "dfl_loss": 0.0,
            "mp": 0.0,  # Mean Precision
            "mr": 0.0,  # Mean Recall
            "map50": 0.0,
            "map50_95": 0.0
        }
        self.lock = threading.Lock()
        
        # 确保 server 目录存在
        (self.workspace_dir / "server").mkdir(parents=True, exist_ok=True)
        # 初始化清空旧日志
        if self.log_file.exists():
            try:
                self.log_file.unlink()
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            # 检查子进程是否已经结束了但状态没更新
            if self.state == "training" and self.process:
                retcode = self.process.poll()
                if retcode is not None:
                    if retcode == 0:
                        self.state = "completed"
                        self.progress["percent"] = 100
                    elif retcode < 0 or self.state == "stopped":
                        self.state = "stopped"
                    else:
                        self.state = "failed"
            
            return {
                "state": self.state,
                "progress": self.progress.copy()
            }

    def start_training(self, train_config: Dict[str, Any]) -> bool:
        with self.lock:
            if self.state in ["preparing", "training"]:
                print("训练已经在进行中...")
                return False

            self.state = "preparing"
            # 重置进度信息
            self.progress = {
                "epoch": 0,
                "total_epochs": train_config.get("epochs", 300),
                "percent": 0,
                "eta": "--:--:--",
                "box_loss": 0.0,
                "seg_loss": 0.0,
                "cls_loss": 0.0,
                "dfl_loss": 0.0,
                "mp": 0.0,
                "mr": 0.0,
                "map50": 0.0,
                "map50_95": 0.0
            }

        # 在单独的线程中执行数据集准备和训练启动
        threading.Thread(target=self._run_train_flow, args=(train_config,), daemon=True).start()
        return True

    def stop_training(self) -> bool:
        with self.lock:
            if self.state not in ["preparing", "training"]:
                return False
            
            self.state = "stopped"
            if self.process:
                try:
                    # Windows 下杀子进程树
                    import platform
                    if platform.system() == "Windows":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], capture_output=True)
                    else:
                        self.process.terminate()
                        self.process.wait(timeout=3)
                except Exception as e:
                    print(f"中止训练进程失败: {e}")
                    try:
                        self.process.kill()
                    except Exception:
                        pass
            return True

    def _run_train_flow(self, config: Dict[str, Any]):
        try:
            # 1. 准备数据集
            from dataset_utils import split_dataset
            
            zip_path = self.workspace_dir / "datasets" / "赶猪通道图集_yolo.zip"
            output_dir = self.workspace_dir / "datasets" / "processed"
            
            # 划分比例
            ratio_str = config.get("split_ratio", "8:1:1")
            try:
                ratios = [float(x) for x in ratio_str.split(":")]
                if len(ratios) == 3:
                    train_r, val_r, test_r = ratios
                else:
                    train_r, val_r, test_r = 0.8, 0.1, 0.1
            except Exception:
                train_r, val_r, test_r = 0.8, 0.1, 0.1

            # 进度：准备中
            self._write_log("[SYSTEM] 正在准备数据集，执行解压缩与划分...\n")
            
            split_res = split_dataset(
                zip_path=str(zip_path),
                output_dir=str(output_dir),
                train_ratio=train_r,
                val_ratio=val_r,
                test_ratio=test_r,
                seed=42
            )
            
            data_yaml_path = split_res["data_yaml"]
            self._write_log(f"[SYSTEM] 数据集划分成功！已写入: {data_yaml_path}\n")

            # 2. 生成运行 Python 脚本
            # 动态生成 YOLO 训练 Python 代码，解决 subprocess CLI 参数传递和环境依赖问题
            model_path = self.workspace_dir / "models" / "yolo26s-seg.pt"
            
            # 使用 utf-8 写入临时 Python 运行脚本
            run_script_content = f"""# -*- coding: utf-8 -*-
import sys
from ultralytics import YOLO

# 解决打印输出时的编码问题
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("[RUNNER] 加载模型 {model_path.as_posix()}...", flush=True)
    model = YOLO(r"{model_path.resolve().as_posix()}")
    
    print("[RUNNER] 开始执行训练...", flush=True)
    model.train(
        data=r"{Path(data_yaml_path).resolve().as_posix()}",
        epochs={config.get("epochs", 300)},
        batch={config.get("batch", 4)},
        lr0={config.get("lr0", 0.001)},
        patience={config.get("patience", 50)},
        imgsz={config.get("imgsz", 960)},
        device="{config.get("device", "cpu")}",
        # 数据增强
        mosaic={config.get("mosaic", 1.0)},
        mixup={config.get("mixup", 0.0)},
        copy_paste={config.get("copy_paste", 0.0)},
        fliplr={config.get("fliplr", 0.5)},
        flipud={config.get("flipud", 0.0)},
        degrees={config.get("degrees", 0.0)},
        # 优化参数
        workers=4,
        project=r"{self.workspace_dir.resolve().as_posix()}/runs",
        name="yolo26s_train",
        exist_ok=True,
        plots=True
    )
    print("[RUNNER] 训练顺利完成！", flush=True)

if __name__ == '__main__':
    main()
"""
            with open(self.runner_file, "w", encoding="utf-8") as f:
                f.write(run_script_content)

            with self.lock:
                if self.state == "stopped":
                    self._cleanup_temp_files()
                    return
                self.state = "training"

            # 3. 运行子进程
            self._write_log("[SYSTEM] 启动训练子进程...\n")
            
            # 用系统的 python 解释器执行生成的脚本
            self.process = subprocess.Popen(
                [sys.executable, str(self.runner_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                cwd=str(self.workspace_dir)
            )

            # 4. 逐行读取子进程输出并解析
            for line in iter(self.process.stdout.readline, ""):
                # 写入日志文件
                self._write_log(line)
                # 解析进度
                self._parse_log_line(line)

            # 等待进程退出
            self.process.wait()
            retcode = self.process.poll()

            with self.lock:
                if self.state == "stopped":
                    self._write_log("[SYSTEM] 训练已被用户手动停止。\n")
                elif retcode == 0:
                    self.state = "completed"
                    self.progress["percent"] = 100
                    self._write_log("[SYSTEM] 训练成功结束。\n")
                else:
                    self.state = "failed"
                    self._write_log(f"[SYSTEM] 训练子进程异常退出，退出码: {retcode}\n")

        except Exception as e:
            with self.lock:
                self.state = "failed"
            self._write_log(f"[SYSTEM] 训练过程发生未知错误: {str(e)}\n")
        finally:
            self._cleanup_temp_files()

    def _write_log(self, text: str):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"写入日志文件失败: {e}")

    def _cleanup_temp_files(self):
        try:
            if self.runner_file.exists():
                self.runner_file.unlink()
        except Exception:
            pass

    def _parse_log_line(self, line: str):
        # 去除前后的空白
        stripped = line.strip()
        
        # 1. 尝试匹配训练进度（例如 Epoch 进度）
        # Ultralytics 训练过程中的 Epoch 行，例如：
        #       1/300      1.24G      1.123      1.456     0.9876      1.221         32        960:
        epoch_match = EPOCH_PROGRESS_PATTERN.match(line)
        if epoch_match:
            try:
                curr_epoch = int(epoch_match.group(1))
                total_epochs = int(epoch_match.group(2))
                
                # 更新进度
                with self.lock:
                    self.progress["epoch"] = curr_epoch
                    self.progress["total_epochs"] = total_epochs
                    self.progress["percent"] = int((curr_epoch - 1) / total_epochs * 100)
                    
                    # 捕获各种 Loss 值
                    # YOLOv8 Seg 训练头部字段是: Epoch, GPU_mem, box_loss, seg_loss, cls_loss, dfl_loss
                    self.progress["box_loss"] = float(epoch_match.group(4))
                    self.progress["seg_loss"] = float(epoch_match.group(5))
                    self.progress["cls_loss"] = float(epoch_match.group(6))
                    self.progress["dfl_loss"] = float(epoch_match.group(7))
            except Exception as e:
                pass
            return

        # 2. 尝试匹配指标行（通常在每个 Epoch 结束的 validation 阶段输出）
        # 例如: "all        103        103      0.823      0.791      0.812      0.543"
        # 或者是多行，如果有 Box 和 Seg 两类指标。YOLO 会在最后汇总打印。
        # 我们用正则提取 metric
        metric_match = METRIC_LINE_PATTERN.match(line)
        if metric_match:
            try:
                # 提取前4个指标：P, R, mAP50, mAP50-95
                val1 = float(metric_match.group(1))
                val2 = float(metric_match.group(2))
                val3 = float(metric_match.group(3))
                val4 = float(metric_match.group(4))
                
                with self.lock:
                    self.progress["mp"] = val1
                    self.progress["mr"] = val2
                    self.progress["map50"] = val3
                    self.progress["map50_95"] = val4
                    # 此时该 Epoch 结束了，更新 percent
                    if self.progress["total_epochs"] > 0:
                        self.progress["percent"] = int(self.progress["epoch"] / self.progress["total_epochs"] * 100)
            except Exception:
                pass

        # 3. 尝试匹配 tqdm 进度条的 ETA 信息，形如 "[00:45<02:30, 4.51it/s]"
        # 我们可以用正则找类似 "<\d+:\d+:\d+" 或 "<\d+:\d+" 的字符
        eta_match = re.search(r'<([0-9:]+)', line)
        if eta_match:
            with self.lock:
                self.progress["eta"] = eta_match.group(1)
