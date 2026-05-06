from playwright.sync_api import sync_playwright
import time
import config
import re
import subprocess
import sys
import hashlib
import os


class JDSpider:
    def _clean_chrome_processes(self):
        try:
            if sys.platform == 'win32':
                subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
        except:
            pass

    def _get_cache_path(self, url):
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        cache_dir = config.TEMP_DIR
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"cache_{url_hash}.html")

    def fetch_html(self, url):
        self._clean_chrome_processes()
        # 如果 URL 没带锚点，我们强行给它加上详情锚点，这能绕过很多点击难题
        if "#detail" not in url:
            url += "#detail"

        with sync_playwright() as p:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=config.CHROME_USER_DATA,
                    executable_path=config.BROWSER_EXE,
                    headless=True,  # 建议 False 观察
                    user_agent=user_agent,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => False });")

                print(f"🔗 正在强行锚点跳转: {url}")
                page.goto(url, wait_until="networkidle", timeout=60000)

                # 1. 暴力滚动：先到底再到中，激活所有异步组件
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(1.5)

                # 2. 核心：直接调用京东内部的 Tab 切换逻辑，不再模拟点击
                print("💉 正在注入 JS 执行 Tab 切换...")
                page.evaluate("""
                    () => {
                        // 寻找那个带 'shangpinjieshao_1' 的 li
                        const target = document.querySelector("li[clstag*='shangpinjieshao_1']");
                        if (target) {
                            target.click(); // 触发点击
                            // 强行把它的 class 改成 current，有时能欺骗一些懒加载逻辑
                            target.parentElement.querySelectorAll('li').forEach(li => li.classList.remove('current'));
                            target.classList.add('current');
                        }
                    }
                """)
                time.sleep(2.5)  # 给参数渲染留够时间

                # 3. 数据提取
                title = self._extract_title(page)
                price = self._extract_price(page)
                specs_string, count = self._extract_specs(page)

                if count == 0:
                    print("🚨 依旧为0，尝试最后一种可能：直接定位参数块 ID 并强制显示")
                    page.evaluate(
                        "document.getElementById('product-detail') ? document.getElementById('product-detail').style.display='block' : null")
                    specs_string, count = self._extract_specs(page)

                print(f"✅ 抓取完成: {title[:12]} | 价格: {price} | 参数: {count}项")

                result_html = f"<meta name='ex-price' content='{price}'><meta name='ex-title' content='{title}'><pre id='ai-specs-block'>{specs_string}</pre>" + page.content()

                with open(self._get_cache_path(url), "w", encoding="utf-8") as f:
                    f.write(result_html)

                context.close()
                return result_html

            except Exception as e:
                print(f"❌ 运行异常: {e}")
                return None

    def _extract_title(self, page):
        try:
            return page.locator(".sku-name").first.inner_text().strip()
        except:
            return "未知商品"

    def _extract_price(self, page):
        try:
            text = page.locator(".p-price .price").first.inner_text()
            return re.search(r'\d+', text).group()
        except:
            return "待定"

    def _extract_specs(self, page):
        """精准提取 TP-LINK 等路由器的硬核参数"""
        # 点击后，务必等待参数节点渲染
        try:
            page.wait_for_selector("#product-attribute .item", timeout=4000)
        except:
            return "抓取失败", 0

        specs = []
        items = page.locator("#product-attribute .item")
        for i in range(items.count()):
            item = items.nth(i)
            try:
                # 按照你提供的 HTML 结构提取
                k = item.locator(".label .text").first.inner_text().strip()
                v = item.locator(".value .text").first.inner_text().strip()
                if k:
                    specs.append(f"{k}: {v}")
            except:
                continue

        return "\n".join(specs), len(specs)