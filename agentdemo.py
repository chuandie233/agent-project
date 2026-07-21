import os
import pandas as pd
from sqlalchemy import create_engine, text
from dashscope import Generation
import dashscope

dashscope.api_key = "sk-ws-H.EMIDEYP.QAvs.MEUCIQDkbQTEuoaFXnFIbSlWu16DNQHq_4siMGm-rDqbPJ7w4gIga8Y0VeFQnW8jhpdl-PzlGC8mXBXfuG7EIXPpE7u8m7o"

# 1. 创建示例数据
data = {
    "地区": ["华东", "华东", "华南", "华南", "华北", "华北"],
    "产品": ["手机", "电脑", "手机", "电脑", "手机", "电脑"],
    "销售额": [12000, 8000, 15000, 9000, 10000, 7000],
    "销量": [120, 80, 150, 90, 100, 70]
}
df = pd.DataFrame(data)

# 2. 保存为 Excel
df.to_excel("销售数据.xlsx", index=False)
print("已生成示例数据：销售数据.xlsx")

# 3. 加载到 SQLite 数据库
engine = create_engine("sqlite:///销售数据.db")
df.to_sql("sales", engine, if_exists="replace", index=False)
print("已加载到数据库")

def ask_agent(question):
    """通义千问生成 SQL，并执行返回结果"""
    
    prompt = f"""你是一个 SQL 专家。表名是 sales，包含以下列：
- 地区 (文本)
- 产品 (文本)
- 销售额 (整数)
- 销量 (整数)

请根据用户问题生成 SQLite 语法兼容的 SQL 查询语句。

用户问题：{question}

要求：
1. 只输出 SQL 语句，不要有其他内容
2. 字符串用单引号，列名不需要引号
3. 如果问"华东"，直接写 WHERE 地区 = '华东'

SQL："""

    response = Generation.call(
        model="qwen-turbo",
        prompt=prompt,
        result_format="message"
    )
    sql = response.output.choices[0].message.content
    print(f"生成的 SQL：{sql}")
    
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()
    
    return rows

if __name__ == "__main__":
    print("\n" + "="*50)
    print("Text2SQL Agent 测试")
    print("="*50)
    
    question = "华东的总销售额是多少？"
    print(f"\n问题：{question}")
    
    result = ask_agent(question)
    print(f"查询结果：{result}")