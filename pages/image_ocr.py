# pages/image_ocr.py
import streamlit as st
import easyocr
from PIL import Image
import numpy as np
import torch

st.set_page_config(page_title="图片文字识别 (OCR)", layout="wide")

st.title("🔍 在线图片转文字 (行列对齐版)")
st.info("已开启坐标对齐算法：自动将水平位置相近的文字合并到同一行。")

# 检测 GPU
gpu_available = torch.cuda.is_available()


@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ch_sim', 'en'], gpu=gpu_available)


reader = load_ocr()


def get_aligned_text(img_array):
    """根据坐标对齐文字的逻辑"""
    # 获取带详细信息的识别结果：[([坐标], '文字', 置信度), ...]
    raw_results = reader.readtext(img_array)

    if not raw_results:
        return "未识别到文字"

    # 1. 将结果转化为易处理的格式，并计算每个块的中心点 Y 坐标
    items = []
    for (bbox, text, prob) in raw_results:
        # bbox 格式: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_start = bbox[0][0]
        items.append({'y': y_center, 'x': x_start, 'text': text})

    # 2. 按 Y 坐标排序
    items.sort(key=lambda x: x['y'])

    # 3. 纵向分组（判断哪些块属于同一行）
    lines = []
    if items:
        current_line = [items[0]]
        for i in range(1, len(items)):
            # 如果当前项与上一项的 Y 坐标差值小于 15 像素（可根据需求调整），视为同一行
            # 这里阈值设为 15-20 比较稳健
            if abs(items[i]['y'] - items[i - 1]['y']) < 20:
                current_line.append(items[i])
            else:
                # 换行前，先对当前行按 X 坐标左右排序
                current_line.sort(key=lambda x: x['x'])
                lines.append(" ".join([obj['text'] for obj in current_line]))
                current_line = [items[i]]
        # 处理最后一行
        current_line.sort(key=lambda x: x['x'])
        lines.append(" ".join([obj['text'] for obj in current_line]))

    return "\n".join(lines)


# 1. 批量上传
uploaded_files = st.file_uploader("选择图片文件", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    st.divider()
    for idx, uploaded_file in enumerate(uploaded_files):
        col_img, col_txt = st.columns([1, 2])
        image = Image.open(uploaded_file)
        img_array = np.array(image)

        with col_img:
            st.write(f"**图片名称:** {uploaded_file.name}")
            st.image(image, use_container_width=True)

        with col_txt:
            # 执行识别
            state_key = f"ocr_res_{uploaded_file.name}_{idx}"
            if state_key not in st.session_state:
                with st.spinner(f"正在分析排版并识别 {uploaded_file.name}..."):
                    full_text = get_aligned_text(img_array)
                    st.session_state[state_key] = full_text

            # 可编辑文本区域
            edited_text = st.text_area(
                f"识别结果 (已尝试对齐) - {uploaded_file.name}",
                value=st.session_state[state_key],
                height=300,
                key=f"edit_{idx}"
            )

            if st.button(f"确认修改并复制文本", key=f"btn_{idx}"):
                st.session_state[state_key] = edited_text
                st.success("内容已保存！")
        st.divider()
else:
    st.warning("请先上传图片。")