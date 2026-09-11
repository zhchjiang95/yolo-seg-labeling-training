# -*- coding: utf-8 -*-
import os
import zipfile
import shutil
import random
import json
from pathlib import Path
from typing import Tuple, Dict, Any, List

def split_dataset(
    zip_path: str,
    output_dir: str,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
    local_dataset_dir: str = None,
    force_re_split: bool = False
) -> Dict[str, Any]:
    """
    解压 ZIP 数据集或直接使用本地已标注目录，按比例划分为 train/val/test 集合，生成 YOLO 格式的数据结构和 data.yaml。
    支持基于 split.json 的增量固化机制：历史图片的划分保持不变，新增图片自动按比例追加分配，避免评估集数据泄露。
    """
    # 确保比例总和为 1
    total_ratio = train_ratio + val_ratio + test_ratio
    if not (0.99 <= total_ratio <= 1.01):
        # 归一化
        train_ratio = train_ratio / total_ratio
        val_ratio = val_ratio / total_ratio
        test_ratio = test_ratio / total_ratio

    # 设置随机种子以保证结果可复现
    random.seed(seed)

    # 路径转换
    output_dir_obj = Path(output_dir)
    
    # 检查是否使用本地已标注数据集
    use_local = False
    if local_dataset_dir:
        local_img_dir = Path(local_dataset_dir) / "images"
        if local_img_dir.exists() and any(local_img_dir.iterdir()):
            use_local = True

    if use_local:
        print(f"使用本地已标注数据集进行划分: {local_dataset_dir}")
        images_dir = Path(local_dataset_dir) / "images"
        labels_dir = Path(local_dataset_dir) / "labels"
        classes_file = Path(local_dataset_dir) / "classes.txt"
        
        # 确保 labels 目录存在
        labels_dir.mkdir(parents=True, exist_ok=True)
    else:
        # 临时解压目录
        temp_extract_dir = output_dir_obj / "temp_extracted"
        if temp_extract_dir.exists():
            shutil.rmtree(temp_extract_dir)
        temp_extract_dir.mkdir(parents=True, exist_ok=True)

        # 1. 解压缩文件
        zip_path_obj = Path(zip_path)
        print(f"正在解压 {zip_path_obj} 到临时目录...")
        try:
            with zipfile.ZipFile(zip_path_obj, 'r') as zip_ref:
                # 解决 zip 解压中文路径乱码问题
                for member in zip_ref.infolist():
                    try:
                        # Windows 下通常使用 cp437 编码，转成 utf-8
                        filename = member.filename.encode('cp437').decode('gbk')
                    except Exception:
                        filename = member.filename
                    
                    target_path = temp_extract_dir / filename
                    # 确保父目录存在
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    if not member.is_dir():
                        with zip_ref.open(member) as source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)
        except Exception as e:
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            raise RuntimeError(f"解压数据集失败: {str(e)}")

        # 2. 定位图片和标签目录，以及 classes.txt
        # 查找 temp_extracted 内部的 images/ 文件夹
        images_dir = None
        labels_dir = None
        classes_file = None

        # 遍历临时解压目录以寻找核心文件夹，兼容多层目录情况
        for root, dirs, files in os.walk(temp_extract_dir):
            root_path = Path(root)
            if "images" in dirs:
                images_dir = root_path / "images"
            if "labels" in dirs:
                labels_dir = root_path / "labels"
            if "classes.txt" in files:
                classes_file = root_path / "classes.txt"

        # 如果没有显式的 images 目录，直接在根目录或子目录下寻找所有图片文件
        if not images_dir:
            # 尝试寻找任何图片格式的文件
            all_imgs = []
            for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.webp'):
                all_imgs.extend(list(temp_extract_dir.rglob(f"*{ext}")))
            if not all_imgs:
                shutil.rmtree(temp_extract_dir)
                raise ValueError("在压缩包中未找到任何图片文件。")
            # 假设存在默认位置
            images_dir = temp_extract_dir / "images"
            labels_dir = temp_extract_dir / "labels"
            images_dir.mkdir(exist_ok=True)
            labels_dir.mkdir(exist_ok=True)
            # 移动图片到 images 文件夹下
            for img_path in all_imgs:
                # 避免死循环移动
                if "images" not in img_path.parts:
                    shutil.move(str(img_path), str(images_dir / img_path.name))

        # 如果有 images 目录但没有 labels 目录，创建一个空的
        if not labels_dir:
            labels_dir = images_dir.parent / "labels"
            labels_dir.mkdir(exist_ok=True)

    # 3. 收集所有的图片，并匹配标签
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.JPG', '.PNG', '.JPEG')
    images_list = [f for f in images_dir.iterdir() if f.is_file() and f.suffix in image_extensions]
    
    if not images_list:
        if not use_local:
            shutil.rmtree(temp_extract_dir)
        raise ValueError("未在 images 目录下找到有效图片文件。")

    # 4. 创建最终的划分子集目录结构（并清空旧文件，避免残留历史文件）
    for split in ['train', 'val', 'test']:
        split_img_dir = output_dir_obj / split / 'images'
        split_lbl_dir = output_dir_obj / split / 'labels'
        if split_img_dir.exists():
            shutil.rmtree(split_img_dir)
        if split_lbl_dir.exists():
            shutil.rmtree(split_lbl_dir)
        split_img_dir.mkdir(parents=True, exist_ok=True)
        split_lbl_dir.mkdir(parents=True, exist_ok=True)

    # 5. 执行增量固化划分（基于 split.json 保护已有数据，防止评估集泄露）
    split_meta_file = Path(local_dataset_dir) / "split.json" if use_local else output_dir_obj / "split.json"
    img_dict = {f.name: f for f in images_list}
    
    splits = {'train': [], 'val': [], 'test': []}
    allocated_names = set()
    
    # 若允许读取历史划分且文件存在
    if split_meta_file.exists() and not force_re_split:
        try:
            with open(split_meta_file, 'r', encoding='utf-8') as f:
                saved_splits = json.load(f)
            
            # 优先继承历史老图片的归属，确保其身份绝对固定
            for split_name in ['train', 'val', 'test']:
                for fname in saved_splits.get(split_name, []):
                    if fname in img_dict:
                        splits[split_name].append(img_dict[fname])
                        allocated_names.add(fname)
            print(f"[DatasetSplit] 成功继承历史 split.json 划分: Train={len(splits['train'])}, Val={len(splits['val'])}, Test={len(splits['test'])}")
        except Exception as e:
            print(f"[DatasetSplit] 读取历史 split.json 失败或格式不兼容，将全新划分: {e}")
            splits = {'train': [], 'val': [], 'test': []}
            allocated_names = set()

    # 找出本次新增的未分配图片
    unallocated_imgs = [f for f in images_list if f.name not in allocated_names]
    
    if unallocated_imgs:
        random.shuffle(unallocated_imgs)
        num_new = len(unallocated_imgs)
        new_train_end = int(num_new * train_ratio)
        new_val_end = new_train_end + int(num_new * val_ratio)
        
        splits['train'].extend(unallocated_imgs[:new_train_end])
        splits['val'].extend(unallocated_imgs[new_train_end:new_val_end])
        splits['test'].extend(unallocated_imgs[new_val_end:])
        
        if allocated_names:
            print(f"[DatasetSplit] 检测到 {num_new} 张增量新图片，已按比例分配并追加至各子集 (Train+{new_train_end}, Val+{new_val_end-new_train_end}, Test+{num_new-new_val_end})")
        else:
            print(f"[DatasetSplit] 初始划分完成: Train={len(splits['train'])}, Val={len(splits['val'])}, Test={len(splits['test'])}")

    # 持久化当前划分结果至 split.json
    try:
        save_data = {
            'train': [f.name for f in splits['train']],
            'val': [f.name for f in splits['val']],
            'test': [f.name for f in splits['test']],
            'total_count': len(images_list),
            'train_ratio': train_ratio,
            'val_ratio': val_ratio,
            'test_ratio': test_ratio
        }
        with open(split_meta_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        # 并在输出训练目录备份一份
        if use_local and output_dir_obj != Path(local_dataset_dir):
            with open(output_dir_obj / "split.json", 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[DatasetSplit] 持久化 split.json 失败: {e}")

    total_count = len(images_list)

    # 6. 获取类别列表
    classes = ["pig"]  # 默认类别
    if classes_file and classes_file.exists():
        try:
            with open(classes_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                if lines:
                    classes = lines
        except Exception as e:
            print(f"读取 classes.txt 失败，使用默认类别 [pig]: {e}")

    # 初始化类别实例统计字典: { cls_name: {'total': 0, 'train': 0, 'val': 0, 'test': 0} }
    class_distribution = {cls_name: {'total': 0, 'train': 0, 'val': 0, 'test': 0} for cls_name in classes}

    # 计数信息
    stats = {
        'total': total_count,
        'train': {'images': len(splits['train']), 'labels': 0, 'negatives': 0, 'instances': 0},
        'val': {'images': len(splits['val']), 'labels': 0, 'negatives': 0, 'instances': 0},
        'test': {'images': len(splits['test']), 'labels': 0, 'negatives': 0, 'instances': 0}
    }

    # 7. 分发文件并精准解析统计每个子集与类别的分布
    for split_name, img_files in splits.items():
        dest_img_dir = output_dir_obj / split_name / 'images'
        dest_lbl_dir = output_dir_obj / split_name / 'labels'

        for img_path in img_files:
            # 复制图片
            shutil.copy2(img_path, dest_img_dir / img_path.name)

            # 寻找对应标签文件（同名，后缀改为 .txt）
            lbl_name = img_path.stem + ".txt"
            lbl_path = labels_dir / lbl_name

            if lbl_path.exists() and lbl_path.is_file():
                with open(lbl_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                
                if content:
                    shutil.copy2(lbl_path, dest_lbl_dir / lbl_name)
                    stats[split_name]['labels'] += 1

                    # 逐行解析标注实例类别
                    for line in content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split()
                        try:
                            cls_id = int(parts[0])
                            cls_name = classes[cls_id] if 0 <= cls_id < len(classes) else f"class_{cls_id}"
                            if cls_name not in class_distribution:
                                class_distribution[cls_name] = {'total': 0, 'train': 0, 'val': 0, 'test': 0}
                            class_distribution[cls_name]['total'] += 1
                            class_distribution[cls_name][split_name] += 1
                            stats[split_name]['instances'] += 1
                        except Exception:
                            pass
                else:
                    # 空白文件视作负样本
                    stats[split_name]['negatives'] += 1
            else:
                # 找不到 label 文件也作为负样本
                stats[split_name]['negatives'] += 1

    # 8. 写入 YOLO 格式的 data.yaml
    # 注意：YOLO 训练时的路径最好是绝对路径，或者相对于执行训练时所在的工作目录的相对路径
    yaml_content = f"""# YOLOv8/v10 Dataset configuration
path: {output_dir_obj.resolve().as_posix()}  # 绝对路径
train: train/images
val: val/images
test: test/images

# Classes
names:
"""
    for idx, cls_name in enumerate(classes):
        yaml_content += f"  {idx}: {cls_name}\n"

    yaml_file_path = output_dir_obj / "data.yaml"
    with open(yaml_file_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

    # 9. 清理临时解压目录
    if not use_local and temp_extract_dir.exists():
        shutil.rmtree(temp_extract_dir)

    # 10. 构建完整的数据集概况与分布画像 (dataset_summary)
    dataset_name = Path(local_dataset_dir).name if local_dataset_dir else "default"
    total_labeled = sum(stats[s]['labels'] for s in ['train', 'val', 'test'])
    total_negatives = sum(stats[s]['negatives'] for s in ['train', 'val', 'test'])
    total_instances = sum(cls_data['total'] for cls_data in class_distribution.values())

    splits_summary = {}
    for s in ['train', 'val', 'test']:
        img_cnt = stats[s]['images']
        splits_summary[s] = {
            'images': img_cnt,
            'percent': round((img_cnt / total_count * 100), 1) if total_count > 0 else 0.0,
            'labels': stats[s]['labels'],
            'negatives': stats[s]['negatives'],
            'instances': stats[s]['instances']
        }

    dataset_summary = {
        'dataset_name': dataset_name,
        'total_images': total_count,
        'labeled_images': total_labeled,
        'negative_images': total_negatives,
        'total_instances': total_instances,
        'classes': classes,
        'splits': splits_summary,
        'class_distribution': class_distribution
    }

    print(f"数据集划分完成。总计: {total_count} 张图片 (正样本: {total_labeled}, 负样本: {total_negatives}, 实例总数: {total_instances})。")
    print(f"训练集: {stats['train']['images']}，验证集: {stats['val']['images']}，测试集: {stats['test']['images']}")
    
    return {
        "status": "success",
        "data_yaml": yaml_file_path.resolve().as_posix(),
        "stats": stats,
        "classes": classes,
        "dataset_summary": dataset_summary
    }

if __name__ == "__main__":
    # 简易本地测试
    try:
        res = split_dataset(
            zip_path="../datasets/赶猪通道图集_yolo.zip",
            output_dir="../datasets/processed",
            train_ratio=0.8,
            val_ratio=0.1,
            test_ratio=0.1
        )
        print("测试完成:", res)
    except Exception as e:
        print("测试出错:", e)
