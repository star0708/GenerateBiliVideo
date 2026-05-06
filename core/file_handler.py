import os
import base64
import re


class FileHandler:
    @staticmethod
    def get_local_images(folder_path):
        """
        核心优化：直接从本地文件夹获取图片路径，并进行自然排序
        """
        if not os.path.exists(folder_path):
            return []

        # 支持的图片格式
        img_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.avif')

        # 获取所有图片路径
        files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(img_extensions)
        ]

        # --- 自然排序逻辑 (1, 2, 10 而不是 1, 10, 2) ---
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split(r'(\d+)', s)]

        files.sort(key=natural_sort_key)
        return files

    @staticmethod
    def to_base64(img_path):
        """
        优化后的转码逻辑：更智能地识别 MIME 类型
        """
        if not img_path or not os.path.exists(img_path):
            return ""

        ext = os.path.splitext(img_path)[1].lower().replace('.', '')

        # 映射 MIME 类型
        mime_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp',
            'avif': 'image/avif'
        }
        mime = mime_map.get(ext, "image/jpeg")

        try:
            with open(img_path, "rb") as f:
                encoded_content = base64.b64encode(f.read()).decode()
                return f"data:{mime};base64,{encoded_content}"
        except Exception as e:
            print(f"❌ 图片转码失败: {img_path}, 错误: {e}")
            return ""

    @staticmethod
    def read_txt_content(txt_path):
        """
        新增：安全读取本地 TXT 参数文件
        """
        if not txt_path or not os.path.exists(txt_path):
            return ""
        try:
            # 优先使用 utf-8，失败则尝试 gbk (处理部分旧文档)
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                with open(txt_path, 'r', encoding='gbk') as f:
                    return f.read()
        except Exception as e:
            print(f"❌ 读取参数文件失败: {txt_path}, 错误: {e}")
            return ""

    # --- 以下保留两个旧方法名，防止旧代码引用时报错，逻辑已简化 ---
    @staticmethod
    def save_uploaded_files(uploaded_files, temp_path):
        """(过时方法) 仅用于兼容旧版 UI 上传的文件"""
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        saved_paths = []
        for i, file in enumerate(uploaded_files):
            save_path = os.path.join(temp_path, f"{str(i).zfill(3)}_{file.name}")
            with open(save_path, "wb") as f:
                f.write(file.getbuffer())
            saved_paths.append(save_path)
        return saved_paths