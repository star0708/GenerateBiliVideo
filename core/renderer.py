from playwright.sync_api import sync_playwright
import time

class PosterRenderer:
    def render_and_save(self, html_content, save_path):
        """执行 Playwright 高清截图"""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.set_content(html_content, wait_until="networkidle")
            # 额外等待确保图片和字体加载完毕
            time.sleep(1.5)
            page.screenshot(path=save_path, full_page=True)
            browser.close()