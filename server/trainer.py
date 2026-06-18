# -*- coding: utf-8 -*-
import os
import sys
import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional

class YOLOTrainer:
    """
    YOLO 训练管理器，负责拉起训练子进程、解析控制台日志并实时维护训练状态和进度。
    """
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.log_file = self.workspace_dir / "server" / "train.log"
        self.config_file = self.workspace_dir / "server" / "temp_config.json"
        self.runner_file = self.workspace_dir / "server" / "temp_run.py"
        
        # 线程安全的状态变量
        self.state = "idle"  # 状态包括: idle (空闲), preparing (数据集准备中), training (训练中), completed (已完成), failed (失败), stopped (已停止)
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
            "mp": 0.0,      # Mean Precision (平均精确度)
            "mr": 0.0,      # Mean Recall (平均召回率)
            "map50": 0.0,   # mAP50 指标
            "map50_95": 0.0 # mAP50-95 指标
        }
        self.lock = threading.Lock()
        
        # 确保 server 目录存在
        (self.workspace_dir / "server").mkdir(parents=True, exist_ok=True)
        
        # 初始化时清空旧的日志文件
        if self.log_file.exists():
            try:
                self.log_file.unlink()
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        """
        获取当前训练的状态与进度详情（对外 API 调用）
        """
        with self.lock:
            # 如果内存状态是 training，但子进程其实已经结束了，更新最终状态
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
        """
        启动训练流程（数据集划分 + 拉起 YOLO 子进程）
        """
        with self.lock:
            # 避免重复拉起多个训练实例
            if self.state in ["preparing", "training"]:
                print("训练任务已在运行中...")
                return False

            self.state = "preparing"
            # 初始化进度信息
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

        # 在独立后台线程中执行，避免阻塞 FastAPI 响应
        threading.Thread(target=self._run_train_flow, args=(train_config,), daemon=True).start()
        return True

    def stop_training(self) -> bool:
        """
        强行中止当前运行的训练进程
        """
        with self.lock:
            if self.state not in ["preparing", "training"]:
                return False
            
            self.state = "stopped"
            if self.process:
                try:
                    # Windows 系统下使用 taskkill 命令递归杀死子进程树，防止僵尸 YOLO 进程残留
                    import platform
                    if platform.system() == "Windows":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], capture_output=True)
                    else:
                        # Linux 下优雅终止并回收到期
                        self.process.terminate()
                        self.process.wait(timeout=3)
                except Exception as e:
                    print(f"强行中止子进程失败: {e}")
                    try:
                        self.process.kill()
                    except Exception:
                        pass
            return True

    def _run_train_flow(self, config: Dict[str, Any]):
        """
        核心训练工作流执行函数（后台线程运行）
        """
        try:
            # 1. 自动执行数据集解压与划分
            from dataset_utils import split_dataset
            
            zip_path = self.workspace_dir / "datasets" / "赶猪通道图集_yolo.zip"
            output_dir = self.workspace_dir / "datasets" / "processed"
            
            # 提取数据集划分配比比例（默认 8:1:1）
            ratio_str = config.get("split_ratio", "8:1:1")
            try:
                ratios = [float(x) for x in ratio_str.split(":")]
                if len(ratios) == 3:
                    train_r, val_r, test_r = ratios
                else:
                    train_r, val_r, test_r = 0.8, 0.1, 0.1
            except Exception:
                train_r, val_r, test_r = 0.8, 0.1, 0.1

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
            self._write_log(f"[SYSTEM] 数据集自动准备完成！已写入 data.yaml: {data_yaml_path}\n")

            # 2. 动态生成临时 YOLO 训练运行 Python 脚本
            # 这样做可以避免多平台 CLI 参数传参乱码，且能独立设置 stdout 编码
            model_path = self.workspace_dir / "models" / "yolo26s-seg.pt"
            
            run_script_content = f"""# -*- coding: utf-8 -*-
import sys
from ultralytics import YOLO

# 强制标准输出与标准错误采用 UTF-8 编码，防止控制台打印中文乱码
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("[RUNNER] 正在加载 YOLO26s-seg 模型...", flush=True)
    model = YOLO(r"{model_path.resolve().as_posix()}")
    
    print("[RUNNER] 开始拉起训练循环...", flush=True)
    model.train(
        data=r"{Path(data_yaml_path).resolve().as_posix()}",
        epochs={config.get("epochs", 300)},
        batch={config.get("batch", 4)},
        lr0={config.get("lr0", 0.001)},
        patience={config.get("patience", 50)},
        imgsz={config.get("imgsz", 960)},
        device="{config.get("device", "0")}",
        # 鱼眼俯拍场景优化后的数据增强默认参数
        mosaic={config.get("mosaic", 0.5)},
        mixup={config.get("mixup", 0.0)},
        copy_paste={config.get("copy_paste", 0.3)},
        fliplr={config.get("fliplr", 0.5)},
        flipud={config.get("flipud", 0.5)},
        degrees={config.get("degrees", 180.0)},
        workers=4,
        project=r"{self.workspace_dir.resolve().as_posix()}/runs",
        name="yolo26s_train",
        exist_ok=True,
        plots=True
    )
    print("[RUNNER] YOLO 训练已顺利完成！", flush=True)

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

            # 3. 运行子进程执行训练
            self._write_log("[SYSTEM] 启动训练子进程...\n")
            
            self.process = subprocess.Popen(
                [sys.executable, str(self.runner_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                cwd=str(self.workspace_dir)
            )

            # 4. 逐行读取子进程控制台输出并捕获解析进度
            for line in iter(self.process.stdout.readline, ""):
                self._write_log(line)
                self._parse_log_line(line)

            # 等待子进程执行完毕并获取退出状态码
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
                    self._write_log(f"[SYSTEM] 训练子进程异常退出，状态码: {retcode}\n")

        except Exception as e:
            with self.lock:
                self.state = "failed"
            self._write_log(f"[SYSTEM] 训练流程发生未捕获异常: {str(e)}\n")
        finally:
            # 清理动态生成的临时 Python 执行文件
            self._cleanup_temp_files()

    def _write_log(self, text: str):
        """
        向日志文件中写入日志记录
        """
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"写入日志文件失败: {e}")

    def _cleanup_temp_files(self):
        """
        清理临时脚本文件
        """
        try:
            if self.runner_file.exists():
                self.runner_file.unlink()
        except Exception:
            pass

    def _parse_log_line(self, line: str):
        """
        正则解析控制台日志，提取指标和训练 Epoch
        """
        # 1. 尝试匹配训练进度（例如 Epoch 进度）
        # 很多情况下，tqdm 进度条的前面会包含 \r 或者终端控制符，所以用 search 代替 match
        # 匹配类似: "  1/300      1.24G      1.123      1.456     0.9876      1.221         32        960:"
        epoch_search = re.search(r'(\d+)/(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+):', line)
        if epoch_search:
            try:
                curr_epoch = int(epoch_search.group(1))
                total_epochs = int(epoch_search.group(2))
                
                # 更新进度结构
                with self.lock:
                    self.progress["epoch"] = curr_epoch
                    self.progress["total_epochs"] = total_epochs
                    if total_epochs > 0:
                        self.progress["percent"] = int((curr_epoch - 1) / total_epochs * 100)
                    
                    # 捕获各种 Loss 值
                    # YOLOv8 Seg 训练字段顺序: Epoch, GPU_mem, box_loss, seg_loss, cls_loss, dfl_loss
                    self.progress["box_loss"] = float(epoch_search.group(4))
                    self.progress["seg_loss"] = float(epoch_search.group(5))
                    self.progress["cls_loss"] = float(epoch_search.group(6))
                    self.progress["dfl_loss"] = float(epoch_search.group(7))
            except Exception:
                pass
            return

        # 2. 尝试匹配指标行（通常在每个 Epoch 结束的 validation 阶段输出）
        # 例如: "all        103        103      0.823      0.791      0.812      0.543"
        # 使用 search 搜寻以避开可能的控制码
        metric_search = re.search(r'all\s+\d+\s+\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+))?', line)
        if metric_search:
            try:
                # 提取前4个指标：P (精确率), R (召回率), mAP50, mAP50-95
                val1 = float(metric_search.group(1))
                val2 = float(metric_search.group(2))
                val3 = float(metric_search.group(3))
                val4 = float(metric_search.group(4))
                
                with self.lock:
                    self.progress["mp"] = val1
                    self.progress["mr"] = val2
                    self.progress["map50"] = val3
                    self.progress["map50_95"] = val4
                    # 此时该 Epoch 结束了，更新 percent 为当前 Epoch 完成度
                    if self.progress["total_epochs"] > 0:
                        self.progress["percent"] = int(self.progress["epoch"] / self.progress["total_epochs"] * 100)
            except Exception:
                pass
            return

        # 3. 尝试匹配 tqdm 进度条的 ETA 信息，形如 "[00:45<02:30, 4.51it/s]"
        eta_match = re.search(r'<([0-9:]+)', line)
        if eta_match:
            with self.lock:
                self.progress["eta"] = eta_match.group(1)
