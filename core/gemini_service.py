import requests, json, re, config, time


class GeminiService:
    def __init__(self, api_key):
        # 统一格式化 Base URL 并载入配置
        self.api_key = api_key
        self.base_url = config.API_BASE_URL.rstrip('/')
        # 【修改点 1】分别载入两个模型配置
        self.model_score = config.MODEL_SCORE  # 专门用于综合评分
        self.model_script = config.MODEL_SCRIPT  # 专门用于口播文案

    def analyze_batch(self, title_list, user_params=None, manual_specs_list=None):
        """核心：全人工驱动。从 TXT 提取简称、价格、过滤参数，并生成 4 条硬核理由"""
        print(f"🤖 AI 正在对 {len(title_list)} 件商品进行参数提取与分析...")

        products_input_data = []
        for i, placeholder in enumerate(title_list):
            manual_text = manual_specs_list[i] if manual_specs_list and i < len(manual_specs_list) else ""

            # 提取原始标题第一行用于日志显示
            first_line_info = manual_text.split('\n')[0] if manual_text else "未知商品"
            # 1. 解析原始参数字典 (Key: Value)
            raw_specs_dict = {}
            if manual_text:
                for line in manual_text.split('\n'):
                    line = line.strip()
                    if not line: continue
                    if ':' in line or '：' in line:
                        line = line.replace('：', ':')
                        parts = line.split(':', 1)
                        raw_specs_dict[parts[0].strip()] = parts[1].strip()

            # 2. 提取价格 (正则匹配数字)
            price_match = re.search(r'价格[:：]\s*[￥¥]?\s*(\d+\.?\d*)', manual_text)
            extracted_price = price_match.group(1) if price_match else ""

            # 3. 严格按用户【对比基准清单】过滤参数，确保海报不撑长
            final_specs_list = []
            if user_params:
                target_keys = [k.strip() for k in user_params.replace('，', ',').replace('\n', ',').split(',') if
                               k.strip()]
                for key in target_keys:
                    found = False
                    for raw_key in raw_specs_dict:
                        # 关键：只要包含就算匹配
                        if key in raw_key:
                            val = raw_specs_dict[raw_key]
                            if val and val not in ["/", "-", "未知", "待定", "None"]:
                                final_specs_list.append({
                                    "label": key,
                                    "value": val
                                })
                                found = True
                                break
                    if not found:
                        print(f"⚠ 未匹配到参数: {key}")
            else:
                # 默认保底逻辑，取前 8 项
                for k, v in list(raw_specs_dict.items()):
                    final_specs_list.append({"label": k, "value": v})

            products_input_data.append({
                "index": i + 1,
                "full_text": manual_text,
                "price": extracted_price,
                "current_specs": final_specs_list
            })

        # --- 深度评审 Prompt：包含精准型号提取与评分分层 ---
        prompt = f"""你现在是 B 站顶级硬核评测 Up 主。请对以下{len(products_input_data)}件商品进行横评评审，并输出 JSON。

        【待处理数据】
        {json.dumps(products_input_data, ensure_ascii=False)}

        【核心输出规范：绝对禁令】
        1. 【顺序红线】：必须严格按照输入列表的先后顺序进行处理和输出。
           - JSON 数组中的第 1 个对象必须是输入数据中的第 1 个商品。
           - 严禁根据评分高低对商品进行重新排序。

        2. 2. 综合竞争力评分 (Dynamic Competitive Grade): 
           【核心原则】：采用“价格分层+绝对实力”的双轨评分制。针对组内价格较低的产品看重“同价位性价比”，针对组内价格较高的产品看重“绝对性能与旗舰体验”。
           评分数值仅限：5, 4.5, 4。
           - 5分（满分推荐）：
             ▶ 对于低价位产品：必须是该价位的“卷王”，配置越级、性价比极高，在同价位段无敌。
             ▶ 对于高价位产品：必须是这组产品中的“绝对机皇/天花板”，拥有组内最强悍的配置和无短板的体验，贵得物有所值。
           - 4.5分（优秀推荐）：
             ▶ 对于低价位产品：符合主流预期，配置均衡且有亮点。
             ▶ 对于高价位产品：性能强悍但并非组内最顶尖，或者对比其高昂售价稍显溢价，但依然属于优秀产品。
           - 4分（普通/避坑）：
             ▶ 无论高低价位：表现中规中矩，或者存在明显的高价低配、智商税、体验严重缩水等问题。
           - JSON 字段名为 "grade"，值必须为数字类型或字符串类型的数字。

           【避坑指南】：
           - 既要保护“平民法拉利”（如：500元做到同级别无敌必须给5分），也要认可“真正的实力派”（如：2000元的顶级旗舰虽然贵，但只要它是本组综合体验最好的产品，同样必须给5分）。
           - 严禁因为旗舰产品价格高，就机械地拉低它的评分。贵不是缺点，高价低配才是。

        3. short_name: 品牌(中英文)型号，必须包含用户熟知的规格标识（如BE5100）。
        4. reasons: 必须输出 4 条（针对该商品在组内的竞争优势）推荐理由，每条严格 < 15 字。
        5. price: 必须原样返回输入数据中的 'price' 字段值，严禁修改数字。
        6. specs 完整性：必须严格包含输入数据中 'current_specs' 里的所有对象，严禁擅自删减或合并参数条目。”

        示例 JSON 结构：
        {{
          "products": [
            {{
              "short_name": "型号简称",
              "grade": 5,
              "reasons": ["优势1", "优势2", "优势3", "优势4"],
              "specs": [ {{"label": "参数名", "value": "真实数值"}} ]
            }}
          ]
        }}
        """

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            print(f"📡 正在调用 {self.model_score} 进行深度横评与型号校准...")

            max_retries = 4

            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": self.model_score,
                            "messages": [{"role": "user", "content": prompt}],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.1
                        },
                        timeout=120
                    )

                    # 如果成功直接跳出循环
                    if response.status_code == 200:
                        break

                    # 如果是429，执行重试
                    if response.status_code == 429:
                        wait_time = 2 ** attempt
                        print(f"⚠ 遇到 429 限流，第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                        time.sleep(wait_time)
                    else:
                        raise Exception(f"API 错误: {response.text}")

                except requests.exceptions.RequestException as e:
                    wait_time = 2 ** attempt
                    print(f"⚠ 请求异常，第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                    time.sleep(wait_time)

            else:
                raise Exception("连续 5 次请求失败，终止程序")

            if response.status_code != 200:
                raise Exception(f"API 错误: {response.text}")
            ai_content = response.json()['choices'][0]['message']['content']

            # 🔧 自动提取 JSON 主体（工业级写法）
            json_match = re.search(r'\{[\s\S]*\}', ai_content)

            if not json_match:
                print("⚠ 没找到 JSON，原始内容：")
                print(ai_content[:500])
                raise Exception("未找到合法 JSON")

            clean_json = json_match.group()

            products_list = json.loads(clean_json).get('products', [])

            # --- 核心：控制台详细评分显示 ---
            print("\n✅ [AI 评审完成] 详细分值与简称校准如下：")
            for res in products_list:
                s_name = res.get('short_name', '未知')
                s_grade = res.get('grade', '0')
                s_reasons = " | ".join(res.get('reasons', []))
                print(f"⭐ 商品: {s_name.ljust(20)} | 评分: {str(s_grade).center(5)}分")

            return products_list

        except Exception as e:
            print(f"🚨 Gemini Service 批量解析崩溃: {str(e)}")
            raise Exception(f"AI 批量解析故障: {str(e)}")

    def generate_script(self, title, products_data, generate_video=True):
        """撰写口播稿：支持单品/多品逻辑，并响应 generate_video 开关"""

        # 1. 拦截逻辑：如果界面没勾选生成视频，直接退出
        if not generate_video:
            print("\n⏭️  检测到未勾选【生成视频】，已自动跳过口播稿撰写。")
            return "未生成视频口播稿。"

        print(f"📝 AI 正在根据提示词撰写视频口播稿: [{title}]...")

        products_info_str = ""
        for p in products_data:
            specs_summary = "\n".join([f"- {s['label']}: {s['value']}" for s in p.get('specs', [])])
            reasons_summary = "、".join(p.get('reasons', []))
            products_info_str += (
                f"商品名称：{p.get('short_name', '未知')}\n"
                f"商品价格：{p.get('price', '待定')}\n"  # 修复了原有 current_price 且标签重复的 Bug
                f"评分等级：{p.get('grade', '4')}分\n"
                f"核心优势：{reasons_summary}\n"
                f"详细参数：\n{specs_summary}\n\n"
            )

        is_single = len(products_data) == 1

        mode_instruction = f"""
        【核心写作侧重点：场景应用】
        1. 内部审题：你必须在写作前分析文章标题《{title}》，识别观众在这一场景下最担心的痛点或最关注的核心参数，但这些分析只用于指导写作，严禁把“审题分析”、分析过程、痛点列表输出到正文。
        2. 参数加权：在介绍每款产品时，你必须优先并重点分析与标题痛点相关的参数（例如：标题讲平嵌，重点讲深度/散热；标题讲游戏，重点讲芯片/刷新率）。
        3. 篇幅比例：与标题场景直接相关的参数解读应占据 70% 的篇幅，其他次要参数一笔带过即可。
        """

        format_instruction = """
        【最终输出格式硬性要求】
        以下所有写作要求只用于约束内容，不是正文模板，严禁把要求里的栏目名原样输出。

        最终只输出一篇可以直接照着念的完整口播稿。

        正文部分严禁输出任何 Markdown 标题、章节标题、结构说明、审题分析、写作分析、分割线、编号清单、项目符号。
        严禁出现这些字样或类似字样：开头引入、产品详情、优缺点并重、总结与选购建议、结尾部分、第一部分、第二部分、第三部分、审题分析、这期大家真正该看什么。

        介绍商品时，不要把商品名单独做成标题，不要写“## 1、某某型号”。
        每款产品可以自然换段，但必须像正常口播一样直接进入正文。
        正确写法示例：“接着说 TP-LINK TL-7DR6430 BE6400，这台我先说结论……”
        错误写法示例：“## 1、TP-LINK TL-7DR6430 BE6400”

        每款产品之间可以换段，但不能使用“---”分割线，不能使用 1、2、3 这种商品小标题。
        总结部分必须写成连续口播段落，不能写成“适合/需求/理由/一句话”的清单。

        只有最后的 SEO 附加项可以保留两个固定标签：【B站视频简介】和【热门标签】。
        """

        # --- 提示词组装 ---
        if is_single:
            script_prompt = f"""你是一名深谙 B 站算法逻辑与带货转化心理的百万级硬核评测与好物分享博主。你的核心人设是**“懂技术、说真话、替兄弟们试错省钱的数码老炮”**。请根据我提供的产品数据，撰写一篇逻辑严密、干货满满且转化率极高的单品/深度精讲口播稿。
{mode_instruction}
{format_instruction}
【参数场景化翻译要求（极度重要）】： 你的受众包含普通家庭用户或数码小白。必须将生硬枯燥的参数全部『翻译』成用户能秒懂的实际生活场景。
严禁干瘪枯燥地罗列数据。
多用生活中的痛点/爽点引发共鸣（例：不只说“144Hz高刷”，要说“玩FPS拉枪跟手，再也不用担心慢人一步”；不只说“磨砂屏”，要说“白天不拉窗帘也不反光，像看书一样护眼”）。

第一部分：【前 15 秒黄金钩子 & 强保姆级引入】 必须生成一个强留人效果的开场白，长度控制在 120~180 字，必须包含以下逻辑：
打招呼：“hello大家好，这里是[UP主名字]”，全篇称呼观众为“兄弟们”或“小伙伴们”。
痛点切入：一句话点出近期品类痛点（如涨价潮、不知道怎么选），引出本期价值。
留人与导流：强调“如果前面没有中意的别着急走开，可能后面总会有一款适合你的。所有产品的链接我们都放在了评论区置顶，可以一键直达。”

第二部分：【产品详情深度拆解】（核心部分） 按照列表顺序，每款产品一个大段落，严禁使用小标题。
字数要求：内容要极度详尽，进行细致的技术拆解与生活场景代入。
优缺点并重（建立信任）：必须包含 1-2 个核心优势分析 + 至少一个明确的缺点、槽点或适用边界（如“质感确实一般”、“不适合某类人群”）。
解除价格封印，强调性价比：将核心技术与【预估价格或补贴政策】结合。使用极具煽动性的促单短语，如“同价位没有对手”、“降维打击”、“六边形战神”、“一顿饭钱就能拿下”、“早买早吃亏”、“直接闭眼入”。

第三部分：【总结与对号入座选购建议】
介绍完所有产品后，增加一个总结段落。
场景化精准推荐：不要泛泛而谈，必须根据“预算 + 细分需求（如：重度游戏玩家/大户型家庭/预算有限的考研党）”给产品定性分发，帮助观众做最后的购买决策。

第四部分：【结尾：强转化互动模板】 必须原封不动加上这一句： “以上就是本期的全部内容啦，所有型号的链接都在评论区置顶了。如果大家还不知道怎么选，欢迎在评论区以【你的预算 + 核心需求】的格式留言，我们下期再见，拜拜！”

第五部分：【SEO 附加项】
【B站视频简介】（约 200 字）：自然融入核心产品词与品类关键词，精炼总结核心看点，吸引点击。
【热门标签】：生成 8-10 个高热度的数码产品相关热门标签（格式：#标签名）。

第六部分：内容编写原则与文本清洗要求（导出前严格自检）
拒绝空洞水话：去掉“震惊、史诗级、天花板”等夸张虚假词汇。严禁使用造成理解门槛的生僻词或小众黑话。
删掉显性连接词：统统删掉“首先、其次、因此、所以、然后、总之、其中”等像说明书一样的词汇。
简化标点与句式：灵活交替使用主动句和被动句增加叙述节奏感，【绝对禁止】在同一分句内同时使用“把”和“被”造成冗余病句。去掉小连接词后的逗号。
参数零篡改：txt参考参数怎么写就怎么写，严禁胡编乱造硬件参数。

待处理数据： 
标题：{title} 
产品数据（务必包含预估价格段/大促价）： 
{products_info_str}
"""
        else:
            script_prompt = f"""你是一名 B 站顶流数码带货博主。你的核心人设是**“懂技术、说真话、替粉丝省钱试错的数码老炮”。请根据我提供的【文章标题】和【产品详情】**，撰写一篇极具亲和力、场景代入感强且转化率极高的视频口播稿。
{mode_instruction}
{format_instruction}
以下是写作要求，只用于指导正文内容，禁止作为正文标题输出。

开场白要求：
必须生成一个强留人效果的开场白，长度控制在 120~180 字。开头要包含“hello大家好，这里是[UP主名字]”，全篇称呼观众为“兄弟们”或“小伙伴们”。用一句话点出近期品类痛点，比如涨价潮、不知道怎么选、型号太多容易买错，引出本期视频价值。开场里要自然带出这句话：“如果前面没有中意的别着急走开，可能后面总会有一款适合你的。所有产品的链接我们都放在了评论区置顶，可以一键直达。”

产品正文要求：
按照输入列表顺序介绍每款产品。每款产品单独成段，但不要使用商品小标题、编号标题、Markdown 标题或分割线。
介绍到具体商品时，直接进入正题，写成自然口播，例如：“接着说 TP-LINK TL-7DR6430 BE6400，这台我先说结论……”
每款产品 400-600 字左右，不要干巴巴地念参数。必须把参数转化为实际体验收益，例如不要只说“支持某某高刷”，要说“玩 FPS 游戏拉枪跟手，再也不用担心慢人一步”。
每款产品必须优缺点并重。夸完核心优势后，必须指出一个明确的缺点、槽点或适用边界，例如“如果你特别看重降噪的话，它可能不太适合你”或“机器质感确实一般”。
必须结合性价比进行点评。对于好产品，可以使用“直接闭眼入”、“绝对不会出错的选择”、“降维打击”、“六边形战神/战士”、“价格屠夫”、“早买早吃亏”等促单表达，但不要过度堆砌。

总结要求：
介绍完所有产品后，写一段自然口播式总结。不能写成清单，不能写成“适合/需求/理由/一句话”的提纲。
必须根据“预算 + 使用场景 + 细分需求”给产品做对号入座推荐，让观众能快速判断自己该买哪款。

结尾要求：
正文最后必须原封不动加上这一句：“以上就是本期的全部内容啦，视频中出现过的所有型号的购买链接，我们都给大家放在了评论区置顶，有需要的小伙伴可以一键直达。如果还不清楚如何挑选，欢迎在评论区以【预算 + 核心需求】的格式留言，我们下期再见，拜拜。”

SEO 附加项要求：
正文结束后，额外生成【B站视频简介】和【热门标签】。
【B站视频简介】约 200 字，自然融入核心产品词与品类关键词，精炼总结核心看点，吸引点击。
【热门标签】生成 8-10 个高热度的数码产品相关热门标签，格式：#标签名。

内容编写原则：
接地气说人话，拒绝说明书式机械播报，去掉“首先、其次、第一点”等生硬连接词。多用口语化比喻。
句式要像朋友面对面聊天一样自然，不要像 PPT 提纲。
通过精准缺点吐槽，立住不恰烂钱的客观人设，降低观众防备心。
参数零篡改：产品参数怎么写就怎么写，严禁胡编乱造硬件参数。

待处理数据： 
文章标题：{title} 
产品列表及参数（包含预估价格）： 
{products_info_str}
"""

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        # --- 新增重试逻辑开始 ---
        max_retries = 4
        response = None

        try:
            print(f"📡 正在生成视频文案，模式: {self.model_script}...")

            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": self.model_script,
                            "messages": [{"role": "user", "content": script_prompt}],
                            "temperature": 0.7
                        },
                        timeout=240
                    )

                    # 如果成功，直接跳出重试循环
                    if response.status_code == 200:
                        break

                    # 如果遇到 429 限流
                    if response.status_code == 429:
                        wait_time = 2 ** attempt
                        print(f"⚠ 稿件生成遇到 429 限流，第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                        time.sleep(wait_time)
                    else:
                        print(f"🚨 API 报错 (状态码 {response.status_code}): {response.text}")
                        # 非 429 错误也尝试重试，或者根据需要直接 raise
                        time.sleep(1)

                except requests.exceptions.RequestException as e:
                    wait_time = 2 ** attempt
                    print(f"⚠ 网络请求异常，第 {attempt + 1} 次重试，等待 {wait_time} 秒... 错误: {e}")
                    time.sleep(wait_time)

            # 检查最终结果
            if not response or response.status_code != 200:
                error_info = response.text if response else "无响应"
                raise Exception(
                    f"API 最终请求失败 (状态码 {response.status_code if response else 'N/A'}): {error_info}")

            print("✨ 视频口播稿撰写完成！")
            # 1. 先把 AI 返回的原始文本拿出来
            raw_script = response.json()['choices'][0]['message']['content']
            # 2. 精准过滤掉所有的双星号（**），替换为空字符串
            clean_script = raw_script.replace('**', '')
            # 兜底清理 Markdown 标题和分割线
            clean_script = re.sub(r'(?m)^\s*#{1,6}\s*', '', clean_script)
            clean_script = re.sub(r'(?m)^\s*---+\s*$', '', clean_script)
            return clean_script

        except Exception as e:
            print(f"🚨 口播稿生成最终失败: {str(e)}")
            raise Exception(f"口播稿生成失败: {str(e)}")