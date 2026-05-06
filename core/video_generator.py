import os
from PIL import Image  # 1. 必须导入 PIL 的 Image

# 兼容性补丁：处理 Pillow 10.0.0 移除 ANTIALIAS 的问题
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# 兼容性处理：尝试两种不同的导入方式
try:
    from moviepy.editor import ImageClip, concatenate_videoclips
except ImportError:
    from moviepy.video.VideoClip import ImageClip
    from moviepy.video.compositing.concatenate import concatenate_videoclips


class VideoGenerator:
    """
    视频生成工具类：负责将渲染好的海报序列合成 1080P 视频
    """

    @staticmethod
    def generate_mp4(video_title, image_paths, duration_per_img, output_root):
        """
        合成 1920x1080 的 MP4 视频
        :param video_title: 视频标题（文件名）
        :param image_paths: 按录入顺序排列的图片路径列表
        :param duration_per_img: 用户在网页设置的单张显示秒数
        :param output_root: 存放 mp4 的 output 目录
        """
        if not image_paths:
            print("⚠️ 警告：没有图片路径，无法生成视频")
            return None

        print(f"🎬 正在合成视频: {video_title}，共 {len(image_paths)} 帧")
        clips = []

        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue

            # 创建图片片段并设置时长
            clip = ImageClip(img_path).set_duration(duration_per_img)

            # 强制适配 1080P (1920x1080)
            # 策略：缩放至高度 1080，宽度自动等比缩放
            clip = clip.resize(height=1080)

            # 宽度补偿：处理黑边逻辑
            if clip.w > 1920:
                clip = clip.crop(x_center=clip.w / 2, width=1920)
            elif clip.w < 1920:
                padding = int((1920 - clip.w) / 2)
                clip = clip.margin(left=padding, right=padding, color=(0, 0, 0))

            clips.append(clip.set_fps(24))

        if not clips:
            return None

        # 按照列表顺序拼接
        final_video = concatenate_videoclips(clips, method="compose")

        # 处理安全的文件名
        safe_title = "".join([c for c in video_title if c.isalnum() or c in (' ', '-', '_')]).strip()
        output_path = os.path.join(output_root, f"{safe_title or 'final_video'}.mp4")

        # 导出视频 (使用 H.264 编码)
        final_video.write_videofile(output_path, fps=24, codec="libx264")
        return output_path