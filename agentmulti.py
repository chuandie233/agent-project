import os
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dashscope import Generation
import dashscope

dashscope.api_key = "sk-ws-H.EMIDEYP.QAvs.MEUCIQDkbQTEuoaFXnFIbSlWu16DNQHq_4siMGm-rDqbPJ7w4gIga8Y0VeFQnW8jhpdl-PzlGC8mXBXfuG7EIXPpE7u8m7o"

# ========== 准备数据 ==========
data = {
    "地区": ["华东", "华东", "华南", "华南", "华北", "华北"],
    "产品": ["手机", "电脑", "手机", "电脑", "手机", "电脑"],
    "销售额": [12000, 8000, 15000, 9000, 10000, 7000],
    "销量": [120, 80, 150, 90, 100, 70],
    "月份": ["2026-01", "2026-01", "2026-01", "2026-01", "2026-01", "2026-01"]
}
df = pd.DataFrame(data)
engine = create_engine("sqlite:///业务数据.db")
df.to_sql("sales", engine, if_exists="replace", index=False)
print("已加载销售数据")

# ========== 工具1：SQL 查询 ==========
def tool_query_sql(question):
    """根据自然语言生成 SQL 并执行查询"""
    prompt = f"""表名 sales，列：地区(文本), 产品(文本), 销售额(整数), 销量(整数), 月份(文本)

用户问题：{question}

生成 SQLite 语法的 SQL 查询，只输出 SQL 语句："""

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

# ========== 工具2：导出报告 ==========
def tool_export_report(question):
    """将查询结果导出为 Excel 报告"""
    rows = tool_query_sql(question)
    
    # 转成 DataFrame
    if rows:
        df_result = pd.DataFrame(rows)
        filename = f"报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_result.to_excel(filename, index=False)
        return f"已生成报告：{filename}"
    return "没有数据可以导出"

# ========== 工具3：总结分析 ==========
def tool_summarize(question):
    """对查询结果进行 AI 总结"""
    rows = tool_query_sql(question)
    
    if not rows:
        return "没有数据可以分析"
    
    prompt = f"""数据：{rows}
用户问题：{question}
请用一段话总结这个数据，不要超过 100 字："""

    response = Generation.call(
        model="qwen-turbo",
        prompt=prompt,
        result_format="message"
    )
    return response.output.choices[0].message.content

# ========== 主 Agent：自动路由 ==========
def multi_agent(user_input):
    """判断用户意图，自动选择工具"""
    
    # 1. 让 AI 判断意图
    intent_prompt = f"""用户说："{user_input}"

判断用户想要什么，从以下选项中选择一个：
- query：查数据、统计、看数字
- export：导出、生成报告、保存为 Excel
- summarize：总结、分析、解读

只回答一个词："""

    response = Generation.call(
        model="qwen-turbo",
        prompt=intent_prompt,
        result_format="message"
    )
    intent = response.output.choices[0].message.content
    print(f"判断意图：{intent}")
    
    # 2. 路由到对应工具
    if "export" in intent.lower():
        return tool_export_report(user_input)
    elif "summarize" in intent.lower():
        return tool_summarize(user_input)
    else:
        result = tool_query_sql(user_input)
        return f"查询结果：{result}"

# ========== 测试 ==========
if __name__ == "__main__":
    print("="*50)
    print("多工具 Agent 测试")
    print("="*50)
    
    tests = [
        "华东地区的总销售额是多少？",
        "统计各地区的销售总和",
        "帮我导出华东地区的销售数据"
    ]
    
    for q in tests:
        print(f"\n问题：{q}")
        result = multi_agent(q)
        print(f"结果：{result}")
