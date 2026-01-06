# Geminicli2api 运行与集成指南

本指南旨在帮助开发者快速部署并集成 `geminicli2api` 代理服务。该服务将 Google 的生成能力转化为全异步、高并发的 OpenAI 兼容接口。

## 1. 快速启动 (Running the Service)

### 1.1 环境要求
- **Python**: 3.10+
- **依赖安装**:
  ```bash
  pip install -r requirements.txt
  ```

### 1.2 认证设置
首次运行前，请确保你拥有 Google 账号的 OAuth 授权。
1. **设置密码**: 编辑 `.env` 或设置环境变量 `GEMINI_AUTH_PASSWORD`（此为代理服务的访问门禁）。
2. **获取凭据**: 本机运行 `python run.py`，根据提示在浏览器完成 Google 登录。成功后会自动生成 `oauth_creds.json`。

### 1.3 运行服务
```bash
# 默认监听端口 8888
python run.py
```

---

## 2. API 集成规范 (Integration Specs)

### 2.1 基础信息
- **Base URL**: `http://localhost:8888/v1`
- **鉴权 Header**: `Authorization: Bearer <你的密码>`

### 2.2 模型选择 (Gemini 3 系列)
推荐使用最新的 **Gemini 3** 模型，通过后缀控制核心能力：
- **基础版**: `gemini-3-flash-preview`, `gemini-3-pro-preview`
- **联网版**: 模型名 + `-search` (自动启用 Google Search)
- **推理版**: 模型名 + `-maxthinking` (分配最大逻辑推理预算)
- **快速版**: 模型名 + `-nothinking` (极速响应，最小推理)

---

## 3. 高级特性 (Advanced Features)

### 3.1 结构化输出 (Structured Output) 🌟
代理完全支持 OpenAI 风格的 `json_schema`。这可以确保模型返回的数据能够被程序直接解析：

```python
# 示例：强制返回 JSON
"response_format": {
    "type": "json_schema",
    "json_schema": {
        "name": "profile",
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }
    }
}
```

### 3.2 全异步高并发 (High Concurrency)
本服务基于 `FastAPI` 和 `httpx` 构建，支持数十个并行请求而不会互相阻塞。
- **注意**: 调用端建议使用 `asyncio` + `httpx` 以获得最佳性能。

### 3.3 自动重试机制 (Robustness)
服务内置了针对 429 (限流) 和 502 (波动) 的自动恢复逻辑：
- 自动解析 Google 的 `retryDelay` 参数进行精准避让。
- 支持流式连接的自动重连（在数据开始传输前）。

---

## 4. 调用示例 (Python)

### 4.1 高并发并行调用示例
利用 `asyncio` 同时发起多个请求，充分利用全异步架构的性能。

```python
import asyncio
import httpx
import time

async def fetch_answer(client, i, question):
    url = "http://localhost:8888/v1/chat/completions"
    headers = {"Authorization": "Bearer YOUR_PASSWORD"}
    payload = {
        "model": "gemini-3-flash-preview",
        "messages": [{"role": "user", "content": question}]
    }
    start = time.time()
    resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
    print(f"请求 {i} 完成，耗时: {time.time()-start:.2f}s")
    return resp.json()["choices"][0]["message"]["content"]

async def main():
    questions = ["什么是黑洞？", "写一段关于春天的诗。", "人工智能的未来？", "如何学好 Python？"]
    async with httpx.AsyncClient() as client:
        # 并行执行所有请求
        tasks = [fetch_answer(client, i, q) for i, q in enumerate(questions)]
        results = await asyncio.gather(*tasks)
        for i, res in enumerate(results):
            print(f"--- 结果 {i} ---\n{res[:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 结构化输出 (JSON Schema) 示例
强制模型返回一个可以直接被程序解析的 JSON 对象。

```python
import httpx
import json

def get_structured_data():
    url = "http://localhost:8888/v1/chat/completions"
    headers = {"Authorization": "Bearer YOUR_PASSWORD"}
    
    # 定义期望的 JSON 结构
    schema = {
        "type": "object",
        "properties": {
            "book_name": {"type": "string"},
            "author": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "rating": {"type": "number"}
        },
        "required": ["book_name", "author", "tags", "rating"]
    }
    
    payload = {
        "model": "gemini-3-flash-preview",
        "messages": [{"role": "user", "content": "推荐一本关于计算机科学的经典书籍。"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "book_info",
                "schema": schema
            }
        }
    }
    
    resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
    content = resp.json()["choices"][0]["message"]["content"]
    
    # 直接解析返回的字符串为字典
    book_data = json.loads(content)
    print(f"书名: {book_data['book_name']}")
    print(f"作者: {book_data['author']}")
    print(f"标签: {', '.join(book_data['tags'])}")

if __name__ == "__main__":
    get_structured_data()
```

### 4.3 进阶：并发流式结构化输出
代理支持在开启 `stream: true` 的同时使用 `json_schema`。这允许你在保持并行性能的同时，实时接收并解析大量结构化数据。

```python
import asyncio
import httpx
import json

async def fetch_stream_json(client, i):
    url = "http://localhost:8888/v1/chat/completions"
    headers = {"Authorization": "Bearer YOUR_PASSWORD"}
    payload = {
        "model": "gemini-3-flash-preview",
        "messages": [{"role": "user", "content": f"任务 {i}: 生成一个随机物品属性"}],
        "stream": True,
        "response_format": {
            "type": "json_schema", 
            "json_schema": {"name": "item", "schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}
        }
    }
    full_text = ""
    async with client.stream("POST", url, json=payload, headers=headers) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:].strip()
                if data_str == "[DONE]": break
                full_text += json.loads(data_str)["choices"][0]["delta"].get("content", "")
    
    result = json.loads(full_text)
    print(f"流 {i} 结果: {result}")
    return result

async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 同时发起 3 个流式 JSON 任务
        await asyncio.gather(*[fetch_stream_json(client, i) for i in range(3)])

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. 故障排除

- **401**: 密码不匹配。
- **429**: 频率限制。服务会自动重试，若持续报错请联系管理员检查 Google 账户配额。
- **500**: 通常与 `GOOGLE_CLOUD_PROJECT` 设置有关，请确保该环境变量已正确配置。

