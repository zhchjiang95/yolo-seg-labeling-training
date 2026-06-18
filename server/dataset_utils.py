# -*- coding: utf-8 -*-
import os
import zipfile
import shutil
import random
from pathlib import Path
from typing import Tuple, Dict, Any, List

def split_dataset(
    zip_path: str,
    output_dir: str,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42
) -> Dict[str, Any]:
    """
    解压 ZIP 数据集并按比例划分为 train/val/test 集合，生成 YOLO 格式的数据结构和 data.yaml。
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
    zip_path_obj = Path(zip_path)
    output_dir_obj = Path(output_dir)
    
    # 临时解压目录
    temp_extract_dir = output_dir_obj / "temp_extracted"
    if temp_extract_dir.exists():
        shutil.rmtree(temp_extract_dir)
    temp_extract_dir.mkdir(parents=True, exist_ok=True)

    # 1. 解压缩文件
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
        shutil.rmtree(temp_extract_dir)
        raise ValueError("未在 images 目录下找到有效图片文件。")

    # 4. 创建最终的划分子集目录结构
    for split in ['train', 'val', 'test']:
        (output_dir_obj / split / 'images').mkdir(parents=True, exist_ok=True)
        (output_dir_obj / split / 'labels').mkdir(parents=True, exist_ok=True)

    # 5. 随机洗牌并划分
    random.shuffle(images_list)
    total_count = len(images_list)
    train_end = int(total_count * train_ratio)
    val_end = train_end + int(total_count * val_ratio)

    splits = {
        'train': images_list[:train_end],
        'val': images_list[train_end:val_end],
        'test': images_list[val_end:]
    }

    # 计数信息
    stats = {
        'total': total_count,
        'train': {'images': len(splits['train']), 'labels': 0, 'negatives': 0},
        'val': {'images': len(splits['val']), 'labels': 0, 'negatives': 0},
        'test': {'images': len(splits['test']), 'labels': 0, 'negatives': 0}
    }

    # 6. 分发文件
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
                # 如果存在标签文件且非空，则复制
                # 如果是空文件（即负样本），也是合法的，我们复制空文件或者不复制皆可。
                # 按照用户的说法，直接把负样本放在 images 文件夹中，不需要在 labels 文件夹生成空文件。
                # 也就是说，如果 labels 中没有或 labels 中是空的，我们就不在目标的 labels 下面生成空文件。
                with open(lbl_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                
                if content:
                    shutil.copy2(lbl_path, dest_lbl_dir / lbl_name)
                    stats[split_name]['labels'] += 1
                else:
                    # 空白文件也视作负样本，不复制（符合用户仅保留 image 不创建 labels 空文件的心智）
                    stats[split_name]['negatives'] += 1
            else:
                # 找不到 label 文件，也作为负样本处理
                stats[split_name]['negatives'] += 1

    # 7. 获取类别列表
    classes = ["pig"]  # 默认类别
    if classes_file and classes_file.exists():
        try:
            with open(classes_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                if lines:
                    classes = lines
        except Exception as e:
            print(f"读取 classes.txt 失败，使用默认类别 [pig]: {e}")

    # 8. 写入 YOLO 格式的 data.yaml
    # 注意：YOLO 训练时的路径最好是绝对路径，或者相对于执行训练时所在的工作目录的相对路径
    # 这里我们使用相对于 output_dir 的相对路径，但写入 data.yaml 时，为了避免 YOLO 寻找出错，
    # 建议将 data.yaml 的 path 设置为 output_dir 的绝对路径。
    
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
    shutil.rmtree(temp_extract_dir)

    print(f"数据集划分完成。总计: {total_count} 张图片。")
    print(f"训练集: {stats['train']['images']}，验证集: {stats['val']['images']}，测试集: {stats['test']['images']}")
    
    return {
        "status": "success",
        "data_yaml": yaml_file_path.resolve().as_posix(),
        "stats": stats,
        "classes": classes
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
