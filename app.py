import streamlit as st
import os
import asyncio
import sys
import subprocess
from jinja2 import Template
from core.gemini_service import GeminiService
from core.file_handler import FileHandler
from core.renderer import PosterRenderer
# 依然保留 import，但不再调用生成逻辑
from core.video_generator import VideoGenerator
import config
from datetime import datetime
import base64

# 初始化异步策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 初始化全局状态与工具类
if 'gemini' not in st.session_state:
    st.session_state.gemini = GeminiService(config.GEMINI_API_KEY)
if 'renderer' not in st.session_state:
    st.session_state.renderer = PosterRenderer()

st.set_page_config(page_title="自动化视频生产流水线", layout="wide")

# --- 标题 ---
st.title("🏭 自动化视频生产流水线 V2.0")

# --- 侧边栏：灵活配置区 ---
with st.sidebar:
    st.header("⚙️ 生产配置")

    tpl_choice = st.selectbox("视觉模板",
                              ["template01.html", "template02.html", "template03.html", "template04.html",
                               "template05.html", "template06.html"])
    # --- 新增代码：平台选择 ---
    platform_choice = st.sidebar.radio("价格参考平台", ["京东", "淘宝"], index=0, horizontal=True)
    platform_label = "JD" if platform_choice == "京东" else "TB"

    st.divider()
    st.header("📋 参数定义")
    param_file = st.file_uploader("上传对比基准参数清单 (.txt)", type="txt", help="用于统一多款商品的对比维度")

    st.divider()
    st.header("🛠️ 任务开关")
    do_script = st.checkbox("📝 需要 AI 写口播稿", value=True)
    # 此处 checkbox 保留 UI，但逻辑中不再执行视频合成
    do_video = st.checkbox("🎬 生成视频帧图片", value=True)

    st.divider()
    st.header("📹 输出设置")
    v_name = st.text_input("视频标题 / 文件名", placeholder="必填，作为项目文件夹名称")
    img_duration = st.slider("单图停留时长 (秒)", 1.0, 10.0, 6.0)

# --- 主界面：本地路径素材扫描 ---
st.subheader("📂 本地素材扫描")

# 初始化勾选队列，用于记录点击顺序
if 'selection_queue' not in st.session_state:
    st.session_state.selection_queue = []

base_path = st.text_input("本地素材根目录路径", placeholder="输入路径后回车扫描，例如：D:\\Products")

if base_path and os.path.exists(base_path):
    # 1. 获取文件夹列表并按修改时间排序
    all_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    # 排序：按修改时间倒序（最新的在前）
    all_dirs.sort(key=lambda d: os.path.getmtime(os.path.join(base_path, d)), reverse=True)

    # 2. 搜索过滤功能
    search_kw = st.text_input("🔍 搜索文件夹关键词...", "").strip().lower()
    display_dirs = [d for d in all_dirs if search_kw in d.lower()] if search_kw else all_dirs

    st.write(f"共扫描到 {len(all_dirs)} 个文件夹，当前显示 {len(display_dirs)} 个")

    # 3. 渲染文件夹列表（带复选框）
    # 使用 container 限制高度，模拟文件列表效果
    with st.container(height=400, border=True):
        for folder_name in display_dirs:
            # 检查当前文件夹是否已在队列中
            is_checked = folder_name in st.session_state.selection_queue

            # 使用 checkbox，并根据点击动作更新 session_state 里的队列
            if st.checkbox(f"📁 {folder_name}", value=is_checked, key=f"chk_{folder_name}"):
                if folder_name not in st.session_state.selection_queue:
                    st.session_state.selection_queue.append(folder_name)
            else:
                if folder_name in st.session_state.selection_queue:
                    st.session_state.selection_queue.remove(folder_name)

    # 4. 显示当前的勾选顺序（让用户确认逻辑顺序）
    if st.session_state.selection_queue:
        st.success(f"✅ 已选择 {len(st.session_state.selection_queue)} 个商品。出场顺序如下：")

        # 修改点：不再使用 " → " 链接，改用 Markdown 的换行列表
        order_md = ""
        for i, name in enumerate(st.session_state.selection_queue):
            order_md += f"**[{i + 1}]** {name}  \n"  # 注意末尾有两个空格表示 Markdown 换行

        st.info(order_md)  # 使用 info 组件承载列表，视觉上更整齐

        if st.button("清空所有选择"):
            st.session_state.selection_queue = []
            st.rerun()

    # 5. 组装 tasks 数据（核心修改：基于 selection_queue 组装）
    tasks = []
    for folder_name in st.session_state.selection_queue:
        folder_full_path = os.path.join(base_path, folder_name)
        all_files = os.listdir(folder_full_path)
        img_exts = ('.png', '.jpg', '.jpeg', '.webp', '.avif')

        # 扫描图片和TXT
        img_paths = [os.path.join(folder_full_path, f) for f in all_files if f.lower().endswith(img_exts)]
        txt_files = [f for f in all_files if f.lower().endswith('.txt')]

        # 读取参数
        manual_specs = ""
        if txt_files:
            manual_specs = FileHandler.read_txt_content(os.path.join(folder_full_path, txt_files[0]))

        tasks.append({
            "title": folder_name,
            "img_local_paths": sorted(img_paths),  # 此处内部按文件名排序
            "manual_specs": manual_specs
        })
else:
    st.info("💡 请在上方输入合法的本地文件夹路径。")

st.divider()

# --- 核心生产逻辑 ---
if st.button("🚀 立即开始生产 (按勾选顺序)", type="primary", use_container_width=True):
    if not v_name:
        st.error("请先在左侧输入『视频标题』。")
    elif not tasks:
        st.warning("请至少在下方列表中勾选一个文件夹。")
    else:
        # 获取侧边栏对比清单内容
        param_content = param_file.getvalue().decode("utf-8") if param_file else None

        # 过滤出有图片和参数的有效任务（本地路径模式）
        valid_tasks_data = [t for t in tasks if t["img_local_paths"] and t["manual_specs"]]
        total_valid = len(valid_tasks_data)

        if total_valid == 0:
            st.error("勾选的文件夹中缺少必要的图片或 TXT 参数文档，请检查。")
        else:
            # 自动打开输出目录
            path = config.OUTPUT_ROOT
            if not os.path.exists(path):
                os.makedirs(path)
            try:
                if sys.platform == 'win32':
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', path])
                else:
                    subprocess.Popen(['xdg-open', path])
            except Exception as e:
                st.error(f"无法打开文件夹: {e}")

            with st.status("🚀 生产线启动中...", expanded=True) as status:
                # 准备 AI 调用的数据
                manual_specs_to_ai = [t["manual_specs"] for t in valid_tasks_data]
                titles_to_ai = [t["title"] for t in valid_tasks_data]

                try:
                    status.update(label="🔍 AI 正在多商品横向对比并提取核心参数...")
                    # 调用带重试机制的 Gemini 服务
                    batch_results = st.session_state.gemini.analyze_batch(
                        titles_to_ai,
                        user_params=param_content,
                        manual_specs_list=manual_specs_to_ai
                    )

                    script_text = ""
                    if do_script:
                        status.update(label="✍️ 参数对比完成，AI 正在撰写全自动口播稿...")
                        script_text = st.session_state.gemini.generate_script(
                            v_name,
                            batch_results,
                        )
                except Exception as e:
                    st.error(f"AI 协作失败: {e}")
                    st.stop()

                # 创建项目文件夹
                timestamp = datetime.now().strftime("%H%M")
                safe_v_name = "".join([c for c in v_name if c.isalnum() or c in ' -_']).strip()
                project_dir = os.path.join(config.OUTPUT_ROOT, f"{safe_v_name}_{timestamp}")
                os.makedirs(project_dir, exist_ok=True)

                # 保存口播稿
                if do_script and script_text:
                    script_filename = f"{safe_v_name}.txt"
                    with open(os.path.join(project_dir, script_filename), "w", encoding="utf-8") as f:
                        f.write(script_text)

                # --- 4. 视觉渲染流程 ---
                for i, data in enumerate(batch_results):
                    # 在本地路径模式下，batch_results 的顺序与 valid_tasks_data 严格对应
                    p_name = data.get('short_name', f"Product_{i + 1}")
                    status.update(
                        label=f"🎨 正在处理商品{i + 1}素材: [{p_name}] ({i + 1}/{total_valid})..."
                    )

                    # 提取首图用于汇总图（Base64 校准）
                    current_task = valid_tasks_data[i]
                    if current_task["img_local_paths"]:
                        first_img_path = current_task["img_local_paths"][0]
                        with open(first_img_path, "rb") as f:
                            img_bytes = f.read()
                        encoded_string = base64.b64encode(img_bytes).decode('utf-8')
                        ext = os.path.splitext(first_img_path)[1].replace('.', '')
                        data['main_img_b64'] = f"data:image/{ext};base64,{encoded_string}"

                    try:
                        clean_p_name = "".join([c for c in p_name if c.isalnum() or c in ' -_']).strip()

                        # 直接获取本地图片路径进行循环渲染
                        img_paths = current_task["img_local_paths"]

                        for j, img_path in enumerate(img_paths):
                            with open(os.path.join(config.TEMPLATE_DIR, tpl_choice), "r", encoding="utf-8") as f:
                                tpl_html = f.read()

                            html_render = Template(tpl_html).render(
                                p=data,
                                img_b64=FileHandler.to_base64(img_path),
                                platform_label=platform_label  # 新增这一行
                            )

                            # 文件名增加序号并保存到独立文件夹
                            poster_name = f"{i + 1}.{clean_p_name}_{j + 1}.png"
                            poster_path = os.path.join(project_dir, poster_name)

                            st.session_state.renderer.render_and_save(html_render, poster_path)

                    except Exception as e:
                        st.error(f"处理第 {i + 1} 组商品 [{p_name}] 时出错: {e}")

                # 5. 生成汇总对比图（分页版）
                status.update(label="📊 正在生成全参数对比汇总图...")
                import math


                def split_products(total):
                    max_per_page = 8
                    pages = math.ceil(total / max_per_page)
                    base = total // pages
                    remainder = total % pages
                    result = []
                    for i in range(pages):
                        if i < remainder:
                            result.append(base + 1)
                        else:
                            result.append(base)
                    return result


                # 收集所有参数 label
                all_labels = []
                for res in batch_results:
                    for spec in res.get('specs', []):
                        if spec['label'] not in all_labels:
                            all_labels.append(spec['label'])
                summary_tpl = os.path.join(
                    config.TEMPLATE_DIR,
                    "summary_template.html"
                )
                if os.path.exists(summary_tpl):
                    with open(summary_tpl, "r", encoding="utf-8") as f:
                        s_tpl_html = f.read()
                    total_products = len(batch_results)

                    # 计算分页结构
                    page_splits = split_products(total_products)
                    total_pages = len(page_splits)
                    start = 0
                    for page_index, count in enumerate(page_splits):
                        end = start + count
                        page_products = batch_results[start:end]
                        s_render = Template(s_tpl_html).render(
                            products=page_products,
                            labels=all_labels,
                            page_num=page_index + 1,
                            total_pages=total_pages
                        )
                        save_name = f"00_参数对比汇总图_{page_index + 1}.png"
                        st.session_state.renderer.render_and_save(
                            s_render,
                            os.path.join(project_dir, save_name)
                        )
                        start = end

                status.update(label="✅ 所有任务已完成！", state="complete")

            st.success(f"🎉 生产任务结束！请在 Output/{project_dir} 目录下查看结果。")