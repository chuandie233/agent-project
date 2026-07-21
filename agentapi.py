import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from dashscope import Generation
import dashscope
from datetime import datetime
import uvicorn

dashscope.api_key = "sk-ws-H.EMIDEYP.QAvs.MEUCIQDkbQTEuoaFXnFIbSlWu16DNQHq_4siMGm-rDqbPJ7w4gIga8Y0VeFQnW8jhpdl-PzlGC8mXBXfuG7EIXPpE7u8m7o"

app = FastAPI(title="Agent API", description="多工具 Agent 的 API 接口")

engine = None

class QueryRequest(BaseModel):
    question: str
    limit: int = 50

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
加 LIMIT {limit}。"""
    response = Generation.call(
        model="qwen-turbo",
        prompt=prompt,
        result_format="message"
    )
    sql = response.output.choices[0].message.content
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()
    return rows

@app.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    global engine
    file_path = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    df = pd.read_excel(file_path)
    engine = create_engine("sqlite:///uploaded_data.db")
    df.to_sql("data", engine, if_exists="replace", index=False)
    os.remove(file_path)
    
    return {"message": f"上传成功，共 {len(df)} 行，列：{df.columns.tolist()}"}

@app.post("/query")
async def query_data(request: QueryRequest):
    global engine
    if engine is None:
        raise HTTPException(status_code=400, detail="请先上传 Excel 文件")
    
    rows = tool_query(request.question, request.limit)
    return {
        "question": request.question,
        "result": [list(row) for row in rows],
        "count": len(rows)
    }

@app.post("/export")
async def export_data(request: QueryRequest):
    global engine
    if engine is None:
        raise HTTPException(status_code=400, detail="请先上传 Excel 文件")
    
    rows = tool_query(request.question, request.limit)
    if not rows:
        return {"message": "没有数据可以导出"}
    
    df = pd.DataFrame(rows)
    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)
    return {"message": f"已导出：{filename}", "file": filename}

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)