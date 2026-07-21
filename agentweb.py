import os
import pandas as pd
import gradio as gr
from sqlalchemy import create_engine, text
from dashscope import Generation
import dashscope
from datetime import datetime
import matplotlib.pyplot as plt
import requests
import json
import time
import re
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

dashscope.api_key = "sk-ws-H.EMIDEYP.QAvs.MEUCIQDkbQTEuoaFXnFIbSlWu16DNQHq_4siMGm-rDqbPJ7w4gIga8Y0VeFQnW8jhpdl-PzlGC8mXBXfuG7EIXPpE7u8m7o"

engine = None
all_dfs = []
chat_history = []
driver = None

# ==================== Excel 相关工具 ====================

def add_files(files, state_files):
    global all_dfs, engine
    if files is None:
        return state_files, "请上传 Excel 文件", "", gr.update(value=None)
    if not isinstance(files, list):
        files = [files]
    if len(files) == 0:
        return state_files, "请上传 Excel 文件", "", gr.update(value=None)
    for file in files:
        if not any(f.name == file.name for f in state_files):
            state_files.append(file)
    if len(state_files) == 0:
        return state_files, "请上传 Excel 文件", "", gr.update(value=None)
    dfs = []
    for file in state_files:
        df = pd.read_excel(file.name)
        dfs.append(df)
    all_dfs = dfs
    combined_df = pd.concat(dfs, ignore_index=True)
    engine = create_engine("sqlite:///uploaded_data.db")
    combined_df.to_sql("data", engine, if_exists="replace", index=False)
    file_list = "\n".join([os.path.basename(f.name) for f in state_files])
    return state_files, f"已添加 {len(state_files)} 个文件，共 {len(combined_df)} 行", file_list, gr.update(value=None)

def get_schema():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='data'")).fetchone()
        if result:
            return result[0]
        return "表名：data，列根据上传文件自动生成"

def tool_query(question, limit=50):
    schema = get_schema()
    prompt = f"""表结构：
{schema}

用户问题：{question}

生成 SQLite 语法的 SQL 查询，只输出 SQL 语句。
注意：如果查询可能返回大量数据，加 LIMIT {limit}。"""
    response = Generation.call(
        model="qwen-turbo",
        prompt=prompt,
        result_format="message"
    )
    sql = response.output.choices[0].message.content
    print(f"SQL: {sql}")
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()
    return rows

def tool_export(question):
    rows = tool_query(question)
    if not rows:
        return "没有数据可以导出"
    df_result = pd.DataFrame(rows)
    filename = f"报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df_result.to_excel(filename, index=False)
    return f"已生成报告：{filename}"

def tool_summarize(question):
    rows = tool_query(question, limit=100)
    if not rows:
        return "没有数据可以分析"
    prompt = f"""数据：{rows}
用户问题：{question}
请用一段话总结这个数据，不超过 100 字："""
    response = Generation.call(
        model="qwen-turbo",
        prompt=prompt,
        result_format="message"
    )
    return response.output.choices[0].message.content

def tool_write_report(question):
    rows = tool_query(question, limit=100)
    if not rows:
        return "没有数据可以生成周报"
    prompt = f"""根据数据：{rows}
用户问题：{question}
生成一份完整周报，包括：本周概况、各区域表现、问题与建议。300字以内。"""
    response = Generation.call(
        model="qwen-turbo",
        prompt=prompt,
        result_format="message"
    )
    return response.output.choices[0].message.content

def tool_plot(question):
    rows = tool_query(question, limit=50)
    if not rows:
        return "没有数据可以画图"
    df = pd.DataFrame(rows)
    if len(df.columns) < 2:
        return "数据列数不足，无法画图"
    x_col = df.columns[0]
    y_col = df.columns[1]
    try:
        df[y_col] = pd.to_numeric(df[y_col])
    except:
        return f"无法将 {y_col} 转为数值，请检查数据"
    df = df.sort_values(by=y_col, ascending=False)
    plt.figure(figsize=(10, 6))
    plt.bar(df[x_col].astype(str), df[y_col])
    title = question
    for word in ["画", "帮我", "请", "一个"]:
        title = title.replace(word, "")
    if len(title) > 20:
        title = title[:20] + "..."
    plt.title(f"{title} 图表")
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    file_title = question
    for word in ["画", "帮我", "请", "一个"]:
        file_title = file_title.replace(word, "")
    if len(file_title) > 10:
        file_title = file_title[:10]
    filename = f"{file_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(filename)
    plt.close()
    return f"已生成图表：{filename}"

def tool_search(question):
    prompt = f"""用户问：{question}
请根据你的知识回答这个问题。如果不知道具体数据，请给出：
1. 这类数据通常从哪里获取
2. 查询这类数据的关键词建议
3. 一个大概的趋势判断
回答要实用、具体。控制在150字以内。"""
    try:
        response = Generation.call(
            model="qwen-turbo",
            prompt=prompt,
            result_format="message"
        )
        return f"搜索结果：{response.output.choices[0].message.content}"
    except Exception as e:
        return f"搜索服务暂时不可用：{str(e)}"

def tool_send_email(question, to_email, subject):
    rows = tool_query(question)
    if not rows:
        return "没有数据可以发送"
    df_result = pd.DataFrame(rows)
    content = f"查询结果如下：\n\n"
    content += df_result.to_string(index=False)
    content += f"\n\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['Subject'] = Header(f"【Agent报告】{subject}", 'utf-8')
        msg['From'] = "linlongsen8@163.com"
        msg['To'] = to_email

        server = smtplib.SMTP_SSL("smtp.163.com", 465)
        server.login("linlongsen8@163.com", "FPYi5frwtPKLccBG")
        server.sendmail("linlongsen8@163.com", [to_email], msg.as_string())
        server.quit()
        return f"邮件已发送至 {to_email}"
    except Exception as e:
        return f"邮件发送失败：{str(e)}"

# ==================== Selenium 网页操作工具 ====================

def init_driver():
    global driver
    try:
        if driver is not None:
            driver.current_url
            return driver
    except:
        print("浏览器会话已失效，重新初始化...")
        driver = None
    if driver is None:
        options = Options()
        options.add_argument("user-data-dir=C:\\Users\\caoqu\\Desktop\\chrome_profile")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        driver_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
    return driver

def get_url_from_ai(site_name):
    prompt = f"""用户说想打开：{site_name}
请提取出这个网站的标准域名（不要带https://，不要带www.，只要主域名）。
比如：哔哩哔哩 → bilibili.com，百度 → baidu.com，抖音 → douyin.com，京东 → jd.com
只输出域名："""
    try:
        response = Generation.call(
            model="qwen-turbo",
            prompt=prompt,
            result_format="message"
        )
        return response.output.choices[0].message.content.strip()
    except:
        return None

def close_popup_general():
    try:
        if "jd.com" in driver.current_url:
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, ".modal-close, .close-btn, .popup-close, .login-close, .dialog-close, a.close, button.close, .close, .j-close")
                if close_btn and close_btn.is_displayed():
                    close_btn.click()
                    time.sleep(0.5)
                    return True
            except:
                pass
            try:
                elements = driver.find_elements(By.XPATH, "//*[text()='×' or text()='X']")
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        el.click()
                        time.sleep(0.5)
                        return True
            except:
                pass
            try:
                driver.execute_script("""
                    var modal = document.querySelector('.modal-wrapper, .JD-modal, .login-modal, [class*="modal"], [class*="popup"]');
                    if (modal) modal.style.display = 'none';
                """)
                return True
            except:
                pass
        selectors = [".modal-close", ".close-btn", ".popup-close", ".login-close", ".dialog-close", "a.close", "button.close", ".close", ".el-dialog__close", ".ant-modal-close", ".van-popup__close"]
        for selector in selectors:
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if close_btn and close_btn.is_displayed():
                    close_btn.click()
                    time.sleep(0.3)
                    return True
            except:
                continue
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.3)
            return True
        except:
            pass
    except:
        pass
    return False

def find_search_box():
    driver = init_driver()
    if "jd.com" in driver.current_url:
        try:
            return WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "key")))
        except:
            pass
        try:
            return driver.find_element(By.NAME, "keyword")
        except:
            pass
    if "douyin.com" in driver.current_url:
        try:
            return driver.find_element(By.CSS_SELECTOR, "input[placeholder*='搜索'], input[name='q'], input[type='search']")
        except:
            pass
    if "taobao.com" in driver.current_url:
        try:
            return driver.find_element(By.NAME, "q")
        except:
            pass
    selectors = ["input#key", "input#search", "input#q", "input#kw", "input#wd", "input[name='q']", "input[name='wd']", "input[name='keyword']", "input[name='search']", "input[placeholder*='搜索']", "input[placeholder*='搜']", "input[placeholder*='Search']", "input.search", "input.search-input", "input.search-key", "input[type='search']", "input[class*='search']"]
    for selector in selectors:
        try:
            search_box = driver.find_element(By.CSS_SELECTOR, selector)
            if search_box and search_box.is_displayed() and search_box.is_enabled():
                return search_box
        except:
            continue
    return None

def tool_web_open(question):
    global driver
    driver = init_driver()
    try:
        driver.current_url
    except:
        driver = init_driver()
    url = get_url_from_ai(question)
    if not url:
        return "无法识别你要打开的网站"
    if not url.startswith("http"):
        url = "https://" + url
    driver.get(url)
    try:
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
    except:
        pass
    close_popup_general()
    time.sleep(1)
    try:
        return f"已打开网页：{url}\n页面标题：{driver.title}"
    except:
        return f"已打开网页：{url}"

def tool_web_search(question):
    global driver
    driver = init_driver()
    try:
        current_url = driver.current_url
        if not current_url or current_url.startswith("about:"):
            driver.get("https://www.baidu.com")
            time.sleep(2)
            driver.execute_script("""
                var searchBox = document.querySelector('input[name="wd"]');
                if (searchBox) {
                    searchBox.value = arguments[0];
                    searchBox.dispatchEvent(new Event('input', {bubbles: true}));
                }
            """, question)
            time.sleep(0.5)
            driver.execute_script("document.querySelector('input[type=\"submit\"]').click();")
            time.sleep(2)
            return f"已在百度搜索：{question}"
    except:
        driver.get("https://www.baidu.com")
        time.sleep(2)
        driver.execute_script("""
            var searchBox = document.querySelector('input[name="wd"]');
            if (searchBox) {
                searchBox.value = arguments[0];
                searchBox.dispatchEvent(new Event('input', {bubbles: true}));
            }
        """, question)
        time.sleep(0.5)
        driver.execute_script("document.querySelector('input[type=\"submit\"]').click();")
        time.sleep(2)
        return f"已在百度搜索：{question}"
    close_popup_general()
    time.sleep(0.5)
    try:
        WebDriverWait(driver, 5).until(lambda d: d.execute_script("return document.readyState") == "complete")
    except:
        pass
    search_box = find_search_box()
    if search_box:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_box)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", search_box)
            search_box.clear()
            search_box.send_keys(question)
            time.sleep(0.5)
            search_box.send_keys("\n")
            time.sleep(2)
            return f"已在当前页面搜索：{question}"
        except Exception as e:
            return f"⚠️ 搜索失败：{str(e)}"
    else:
        driver.get("https://www.baidu.com")
        time.sleep(2)
        driver.execute_script("""
            var searchBox = document.querySelector('input[name="wd"]');
            if (searchBox) {
                searchBox.value = arguments[0];
                searchBox.dispatchEvent(new Event('input', {bubbles: true}));
            }
        """, question)
        time.sleep(0.5)
        driver.execute_script("document.querySelector('input[type=\"submit\"]').click();")
        time.sleep(2)
        return f"已在百度搜索：{question}"

def tool_web_screenshot():
    global driver
    driver = init_driver()
    try:
        driver.current_url
    except:
        driver = init_driver()
    if driver is None:
        return "请先打开一个网页"
    try:
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    except:
        pass
    time.sleep(2)
    close_popup_general()
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(0.5)
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    try:
        driver.save_screenshot(filename)
        return f"已保存截图：{filename}"
    except Exception as e:
        time.sleep(2)
        try:
            driver.save_screenshot(filename)
            return f"已保存截图（重试）：{filename}"
        except:
            return f"截图失败：{str(e)}"

# ==================== AI 意图解析 ====================

def parse_user_intent(question):
    """用 AI 解析用户意图，返回步骤列表"""
    prompt = f"""用户说："{question}"

请把这句话拆分成独立的操作步骤，按顺序列出，每行一个步骤。
每个步骤用括号标注类型，类型只能是：open, search, screenshot, query, export, summarize, report, plot, email

例如：
用户说："打开抖音搜索手机并截图"
输出：
(open)打开抖音
(search)搜索手机
(screenshot)截图

用户说："华东总销售额多少"
输出：
(query)华东总销售额多少

用户说："画各地区销售额图"
输出：
(plot)画各地区销售额图

用户说："打开京东搜索电脑并截图"
输出：
(open)打开京东
(search)搜索电脑
(screenshot)截图

现在请解析："{question}"

只输出步骤列表，每行一个，不要有其他内容。"""

    try:
        response = Generation.call(
            model="qwen-turbo",
            prompt=prompt,
            result_format="message"
        )
        content = response.output.choices[0].message.content
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        steps = []
        for line in lines:
            match = re.match(r'\((\w+)\)(.+)', line)
            if match:
                step_type = match.group(1)
                step_content = match.group(2).strip()
                steps.append({"type": step_type, "content": step_content})
            else:
                if "打开" in line or "访问" in line:
                    steps.append({"type": "open", "content": line})
                elif "搜索" in line:
                    steps.append({"type": "search", "content": line})
                elif "截图" in line:
                    steps.append({"type": "screenshot", "content": line})
                elif "导出" in line:
                    steps.append({"type": "export", "content": line})
                elif "画图" in line or "图表" in line:
                    steps.append({"type": "plot", "content": line})
                elif "总结" in line or "分析" in line:
                    steps.append({"type": "summarize", "content": line})
                elif "报告" in line or "周报" in line:
                    steps.append({"type": "report", "content": line})
                elif "邮件" in line or "发送" in line:
                    steps.append({"type": "email", "content": line})
                else:
                    steps.append({"type": "query", "content": line})
        
        print(f"AI 解析步骤：{steps}")
        return steps
    except Exception as e:
        print(f"解析失败：{e}")
        return [{"type": "query", "content": question}]

# ==================== 主 Agent ====================

def ask_agent(question, history):
    global engine, chat_history

    steps = parse_user_intent(question)

    excel_types = ["query", "export", "summarize", "report", "plot", "email"]
    need_excel = any(s["type"] in excel_types for s in steps)
    
    if need_excel and engine is None:
        history.append({"role": "assistant", "content": "⚠️ 请先上传 Excel 文件"})
        return history, ""

    results = []
    for step in steps:
        step_type = step["type"]
        content = step["content"]
        
        if step_type == "open":
            result = tool_web_open(content)
        elif step_type == "search":
            keyword = content.replace("搜索", "").strip()
            if not keyword:
                keyword = "手机"
            result = tool_web_search(keyword)
        elif step_type == "screenshot":
            result = tool_web_screenshot()
        elif step_type == "query":
            result = tool_query(content)
            result = f"查询结果：{result}"
        elif step_type == "export":
            result = tool_export(content)
        elif step_type == "summarize":
            result = tool_summarize(content)
        elif step_type == "report":
            result = tool_write_report(content)
        elif step_type == "plot":
            result = tool_plot(content)
        elif step_type == "email":
            result = "请使用下方「发送邮件」功能区"
        elif step_type == "search_info":
            result = tool_search(content)
        else:
            result = f"未知操作：{content}"
        
        results.append(f"[{step_type}] {result}")

    answer = "\n".join(results)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    return history, ""

def send_email_with_agent(question, to_email, subject):
    if engine is None:
        return "请先上传 Excel 文件"
    return tool_send_email(question, to_email, subject)

def clear_all(state_files):
    global engine, all_dfs, chat_history
    engine = None
    all_dfs = []
    chat_history = []
    return [], "已清空所有数据", ""

def clear_chat():
    global chat_history
    chat_history = []
    return []

# ==================== 界面 ====================

with gr.Blocks(title="多工具 Agent") as demo:
    gr.Markdown("# 多工具 Agent 智能助手")
    gr.Markdown("上传 Excel 或直接使用网页操作功能，AI 自动理解你的意图")

    file_state = gr.State([])

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Excel 数据工具")
            file_input = gr.File(
                label="拖拽或点击上传 Excel（可多选）",
                file_types=[".xlsx", ".xls"],
                file_count="multiple"
            )
            with gr.Row():
                clear_btn = gr.Button("清空数据")
            status = gr.Textbox(label="状态")
            file_list = gr.Textbox(label="已上传文件列表", lines=3)

            gr.Markdown("---")
            gr.Markdown("### 发送邮件")
            email_question = gr.Textbox(label="查询问题", placeholder="例如：华东总销售额")
            email_to = gr.Textbox(label="收件人邮箱", placeholder="xxxx@qq.com")
            email_subject = gr.Textbox(label="邮件主题", placeholder="销售数据报告")
            email_btn = gr.Button("发送邮件", variant="primary")
            email_status = gr.Textbox(label="邮件状态")

        with gr.Column(scale=1):
            gr.Markdown("### 对话控制")
            chatbot = gr.Chatbot(label="对话记录", height=400)
            with gr.Row():
                question = gr.Textbox(label="输入指令", placeholder="例如：打开抖音搜索手机并截图 或 华东总销售额多少", scale=4)
                clear_chat_btn = gr.Button("清空对话", scale=1)
            ask_btn = gr.Button("执行", variant="primary")

    file_input.upload(
        add_files,
        inputs=[file_input, file_state],
        outputs=[file_state, status, file_list, file_input]
    )
    clear_btn.click(clear_all, inputs=[file_state], outputs=[file_state, status, file_list])
    clear_chat_btn.click(clear_chat, outputs=chatbot)
    ask_btn.click(ask_agent, inputs=[question, chatbot], outputs=[chatbot, question])
    question.submit(ask_agent, inputs=[question, chatbot], outputs=[chatbot, question])
    email_btn.click(
        send_email_with_agent,
        inputs=[email_question, email_to, email_subject],
        outputs=email_status
    )

if __name__ == "__main__":
    demo.launch(share=True)