import os
import time
import gradio as gr
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from dashscope import Generation
import dashscope

dashscope.api_key = "sk-ws-H.EMIDEYP.QAvs.MEUCIQDkbQTEuoaFXnFIbSlWu16DNQHq_4siMGm-rDqbPJ7w4gIga8Y0VeFQnW8jhpdl-PzlGC8mXBXfuG7EIXPpE7u8m7o"

driver = None
chat_history = []

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
        # 保存用户数据（Cookie、登录状态）
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
        print("浏览器已重新初始化")
    return driver

def get_url_from_ai(site_name):
    prompt = f"""用户说想打开：{site_name}
请提取出这个网站的标准域名（不要带https://，不要带www.，只要主域名）。
比如：哔哩哔哩 → bilibili.com
百度 → baidu.com
抖音 → douyin.com
京东 → jd.com
淘宝 → taobao.com

只输出域名，不要有其他内容："""

    try:
        response = Generation.call(
            model="qwen-turbo",
            prompt=prompt,
            result_format="message"
        )
        url = response.output.choices[0].message.content.strip()
        print(f"AI 解析域名：{site_name} → {url}")
        return url
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
        
        selectors = [
            ".modal-close", ".close-btn", ".popup-close", ".login-close",
            ".dialog-close", "a.close", "button.close", ".close",
            ".el-dialog__close", ".ant-modal-close", ".van-popup__close"
        ]
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
            wait = WebDriverWait(driver, 5)
            search_box = wait.until(EC.presence_of_element_located((By.ID, "key")))
            return search_box
        except:
            pass
        try:
            search_box = driver.find_element(By.NAME, "keyword")
            return search_box
        except:
            pass
    
    if "douyin.com" in driver.current_url:
        try:
            search_box = driver.find_element(By.CSS_SELECTOR, "input[placeholder*='搜索'], input[name='q'], input[type='search']")
            return search_box
        except:
            pass
    
    if "taobao.com" in driver.current_url:
        try:
            search_box = driver.find_element(By.NAME, "q")
            return search_box
        except:
            pass
    
    selectors = [
        "input#key", "input#search", "input#q", "input#kw", "input#wd",
        "input[name='q']", "input[name='wd']", "input[name='keyword']",
        "input[name='search']", "input[placeholder*='搜索']",
        "input[placeholder*='搜']", "input[placeholder*='Search']",
        "input.search", "input.search-input", "input.search-key",
        "input[type='search']", "input[class*='search']"
    ]
    
    for selector in selectors:
        try:
            search_box = driver.find_element(By.CSS_SELECTOR, selector)
            if search_box and search_box.is_displayed() and search_box.is_enabled():
                return search_box
        except:
            continue
    return None

def tool_search_web(question):
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
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
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

def tool_open_website(question):
    global driver
    driver = init_driver()
    
    try:
        driver.current_url
    except:
        driver = init_driver()

    url = get_url_from_ai(question)
    if not url:
        return "无法识别你要打开的网站，请说清楚网站名称"

    if not url.startswith("http"):
        url = "https://" + url

    driver.get(url)
    
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except:
        pass

    close_popup_general()
    time.sleep(1)

    try:
        title = driver.title
        return f"已打开网页：{url}\n页面标题：{title}"
    except:
        return f"已打开网页：{url}"

def tool_screenshot():
    global driver
    driver = init_driver()
    
    try:
        driver.current_url
    except:
        driver = init_driver()
    
    if driver is None:
        return "请先打开一个网页"

    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except:
        pass

    time.sleep(2)
    close_popup_general()
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(0.5)

    filename = f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
    try:
        driver.save_screenshot(filename)
        return f"已保存截图：{filename}"
    except Exception as e:
        time.sleep(2)
        try:
            driver.save_screenshot(filename)
            return f"已保存截图（重试）：{filename}"
        except Exception as e2:
            return f"截图失败：{str(e2)}"

def split_question(question):
    prompt = f"""用户说："{question}"
请把这句话拆分成独立的步骤，按顺序列出，每行一个步骤。
只输出步骤列表，不要有其他内容。

例如：
用户说："打开京东搜索手机并截图"
输出：
打开京东
搜索手机
截图

现在请拆分："{question}" """

    try:
        response = Generation.call(
            model="qwen-turbo",
            prompt=prompt,
            result_format="message"
        )
        content = response.output.choices[0].message.content
        parts = [p.strip() for p in content.split('\n') if p.strip()]
        print(f"AI 拆分步骤：{parts}")
        return parts
    except:
        if "并" in question:
            return [p.strip() for p in question.split("并") if p.strip()]
        return [question]

def ask_agent(question, history):
    global chat_history

    parts = split_question(question)
    results = []
    step_failed = False

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        
        if step_failed:
            results.append(f"步骤{i+1}：⚠️ 上一步骤失败，已跳过")
            continue

        if "截图" in part:
            result = tool_screenshot()
        elif "搜索" in part:
            keyword = part.replace("搜索", "").strip()
            if not keyword:
                keyword = "手机"
            result = tool_search_web(keyword)
        elif "打开" in part or "访问" in part or "去" in part:
            result = tool_open_website(part)
        else:
            result = tool_open_website(part)

        if "⚠️" in result:
            step_failed = True
            results.append(f"步骤{i+1}：{result}（后续步骤已跳过）")
        else:
            results.append(f"步骤{i+1}：{result}")

    answer = "\n".join(results)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    return history, ""

def clear_chat():
    global chat_history
    chat_history = []
    return []

with gr.Blocks(title="Agent Selenium") as demo:
    gr.Markdown("# Agent Selenium 网页操作助手")
    gr.Markdown("让 Agent 帮你搜索、打开网页、截图（登录状态自动保存）")

    with gr.Row():
        with gr.Column():
            chatbot = gr.Chatbot(label="对话记录", height=500)
            with gr.Row():
                question = gr.Textbox(label="输入指令", placeholder="例如：打开抖音搜索手机并截图", scale=4)
                clear_btn = gr.Button("清空", scale=1)
            ask_btn = gr.Button("执行", variant="primary")

    ask_btn.click(ask_agent, inputs=[question, chatbot], outputs=[chatbot, question])
    question.submit(ask_agent, inputs=[question, chatbot], outputs=[chatbot, question])
    clear_btn.click(clear_chat, outputs=chatbot)

if __name__ == "__main__":
    demo.launch(share=True)