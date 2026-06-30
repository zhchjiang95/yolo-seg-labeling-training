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

            self._write_log("[SYSTEM] 正在准备数据集，执行数据划分...\n")
            
            split_res = split_dataset(
                zip_path=str(zip_path),
                output_dir=str(output_dir),
                train_ratio=train_r,
                val_ratio=val_r,
                test_ratio=test_r,
                seed=42,
                local_dataset_dir=str(self.workspace_dir / "datasets" / "labeling" / config.get("dataset", "default"))
            )
            
            data_yaml_path = split_res["data_yaml"]
            self._write_log(f"[SYSTEM] 数据集自动准备完成！已写入 data.yaml: {data_yaml_path}\n")

            # 提前创建训练结果目录并保存训练元数据（如所用数据集），方便后续空闲时查询
            save_dir = self.workspace_dir / "runs" / "segment" / "yolo26s_train"
            save_dir.mkdir(parents=True, exist_ok=True)
            try:
                train_meta = {
                    "dataset": config.get("dataset", "default"),
                    "epochs": config.get("epochs", 300),
                    "batch": config.get("batch", 4),
                    "lr0": config.get("lr0", 0.001),
                    "patience": config.get("patience", 50),
                    "imgsz": config.get("imgsz", 960),
                    "device": config.get("device", "0"),
                    "split_ratio": config.get("split_ratio", "8:1:1"),
                    "mosaic": config.get("mosaic", 0.5),
                    "mixup": config.get("mixup", 0.0),
                    "copy_paste": config.get("copy_paste", 0.3),
                    "fliplr": config.get("fliplr", 0.5),
                    "flipud": config.get("flipud", 0.5),
                    "degrees": config.get("degrees", 180.0)
                }
                with open(save_dir / "train_meta.json", "w", encoding="utf-8") as f:
                    json.dump(train_meta, f, ensure_ascii=False, indent=4)
            except Exception as e:
                self._write_log(f"[SYSTEM] 写入 train_meta.json 失败: {str(e)}\n")

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

            # 3. 运行子进程执行训练，并强制无缓冲输出以实时捕获 tqdm
            self._write_log("[SYSTEM] 启动训练子进程...\n")
            
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            self.process = subprocess.Popen(
                [sys.executable, str(self.runner_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                cwd=str(self.workspace_dir),
                env=env
            )

            # 定义实时按字符读取以兼顾 \r 和 \n 的生成器，从而即时捕捉 tqdm 进度条更新
            def read_lines_realtime(stream):
                buffer = []
                prev_char = ""
                while True:
                    char = stream.read(1)
                    if not char:
                        if buffer:
                            yield "".join(buffer)
                        break
                    
                    if char == '\n' and prev_char == '\r':
                        # 如果是紧随 \r 后面的 \n，说明是 \r\n 换行符的后半截，直接忽略
                        prev_char = char
                        continue
                        
                    if char in ('\r', '\n'):
                        yield "".join(buffer) + char
                        buffer = []
                    else:
                        buffer.append(char)
                    prev_char = char

            # 4. 逐行读取子进程控制台输出并捕获解析进度（实时捕捉 \r 和 \n）
            for line in read_lines_realtime(self.process.stdout):
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
        # 1. 尝试匹配 tqdm 进度条的 ETA 信息，形如 "[00:45<02:30, 4.51it/s]" 或 Ultralytics 独特的 "10.0s<50.0s"、"1:15<2:30"
        # 移到最前面，且匹配成功后不 return，以防止在一行同时包含 Epoch 进度和进度条时被提前拦截
        eta_match = re.search(r'\b([0-9:.]+s?)<([0-9:.]+s?)', line)
        if eta_match:
            with self.lock:
                self.progress["eta"] = eta_match.group(2)


        # 2. 尝试匹配训练进度（例如 Epoch 进度）
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

        # 3. 尝试匹配指标行（通常在每个 Epoch 结束的 validation 阶段输出）
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

    def get_last_run_info(self) -> Dict[str, Any]:
        """
        获取最近一次训练的结果信息（指标、数据集名称、模型状态等）
        """
        run_dirs = [
            self.workspace_dir / "runs" / "segment" / "yolo26s_train",
            self.workspace_dir / "runs" / "yolo26s_train"
        ]
        
        target_dir = None
        for d in run_dirs:
            if d.exists() and d.is_dir():
                target_dir = d
                break
                
        if not target_dir:
            return {"has_data": False}
            
        results_csv = target_dir / "results.csv"
        weights_dir = target_dir / "weights"
        best_pt = weights_dir / "best.pt" if weights_dir.exists() else None
        
        has_best_weight = best_pt.exists() if best_pt else False
        
        # 1. 读取 train_meta.json 获取数据集名称及元配置
        dataset_name = "未知数据集"
        meta_info = {}
        meta_file = target_dir / "train_meta.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta_info = json.load(f)
                    dataset_name = meta_info.get("dataset", "default")
            except Exception:
                pass
        else:
            # 兼容：如果不存在 train_meta.json 则尝试解析 args.yaml 获取配置
            args_file = target_dir / "args.yaml"
            if args_file.exists():
                try:
                    import yaml
                    with open(args_file, "r", encoding="utf-8") as f:
                        args_data = yaml.safe_load(f)
                        if args_data:
                            meta_info["epochs"] = args_data.get("epochs", 300)
                            meta_info["batch"] = args_data.get("batch", 4)
                            meta_info["imgsz"] = args_data.get("imgsz", 960)
                            data_path = args_data.get("data")
                            if data_path:
                                dataset_name = "已完成训练的数据集"
                except Exception:
                    pass

        # 2. 读取 results.csv 解析最终指标
        metrics = {
            "epoch": 0,
            "box_loss": 0.0,
            "seg_loss": 0.0,
            "cls_loss": 0.0,
            "map50": 0.0,
            "map50_95": 0.0
        }
        
        if results_csv.exists():
            try:
                with open(results_csv, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                    if len(lines) > 1:
                        # 解析表头
                        headers = [h.strip() for h in lines[0].split(",")]
                        # 解析最后一行
                        last_line_data = [d.strip() for d in lines[-1].split(",")]
                        
                        row = {}
                        for h, val in zip(headers, last_line_data):
                            try:
                                row[h] = float(val)
                            except ValueError:
                                row[h] = val
                                
                        # 寻找已训练的实际 epoch
                        for h in headers:
                            if "epoch" in h.lower():
                                metrics["epoch"] = int(row[h])
                                break
                                
                        # 兼容并选取最佳 Loss (若有验证集则优先用 val，否则用 train)
                        loss_keys = {
                            "box_loss": ["val/box_loss", "train/box_loss", "box_loss"],
                            "seg_loss": ["val/seg_loss", "train/seg_loss", "seg_loss"],
                            "cls_loss": ["val/cls_loss", "train/cls_loss", "cls_loss"]
                        }
                        
                        for metric_name, possible_headers in loss_keys.items():
                            for p_h in possible_headers:
                                if p_h in row:
                                    metrics[metric_name] = row[p_h]
                                    break
                                    
                        # 选取分割 mAP (优先选择 metrics/mAP50(M) 掩码指标)
                        map50_keys = ["metrics/mAP50(M)", "metrics/mAP50(B)", "val/mAP50", "mAP50"]
                        for k in map50_keys:
                            if k in row:
                                metrics["map50"] = row[k]
                                break
                            found = False
                            for h in headers:
                                if "map50" in h.lower() and "(m)" in h.lower():
                                    metrics["map50"] = row[h]
                                    found = True
                                    break
                            if found:
                                break
                                
                        map50_95_keys = ["metrics/mAP50-95(M)", "metrics/mAP50-95(B)", "val/mAP50-95", "mAP50-95"]
                        for k in map50_95_keys:
                            if k in row:
                                metrics["map50_95"] = row[k]
                                break
                            found = False
                            for h in headers:
                                if "map50-95" in h.lower() and "(m)" in h.lower():
                                    metrics["map50_95"] = row[h]
                                    found = True
                                    break
                            if found:
                                break
            except Exception as e:
                print(f"解析 results.csv 失败: {e}")
                
        # 检查 results.png 是否存在并提供静态可访问相对 URL
        results_png = target_dir / "results.png"
        has_results_png = results_png.exists()
        try:
            rel_results_png = f"/runs/{results_png.relative_to(self.workspace_dir / 'runs').as_posix()}"
        except Exception:
            rel_results_png = ""

        return {
            "has_data": True,
            "dataset": dataset_name,
            "has_best_weight": has_best_weight,
            "metrics": metrics,
            "meta": meta_info,
            "results_png": rel_results_png if has_results_png else ""
        }

