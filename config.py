import os

# 1. 核心接口配置
API_BASE_URL = "https://api.bltcy.ai/v1"
GEMINI_API_KEY = "sk-2cqjWP3vdIiisAtV8rGU5Tr6yk4lMHGHkUviO5YS3XVkXjBk"
# MODEL_SCORE = "gemini-3-pro-preview"  # 评分用轻量快速模型
# MODEL_SCRIPT = "gemini-3.1-pro-preview"   # 写稿用高智能长文本模型
MODEL_SCORE = "gpt-5.4"
MODEL_SCRIPT = "gpt-5.4"

# 2. 浏览器与登录配置 (回归你原来的 D 盘路径)
# BROWSER_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# CHROME_USER_DATA = r"D:\JD_Robot_Edge_Data"

# 3. 目录配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_ROOT = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# 确保输出目录存在
for d in [OUTPUT_ROOT, TEMP_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)