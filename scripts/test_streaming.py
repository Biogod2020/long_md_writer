#!/usr/bin/env python3
"""
测试 geminicli2api 的 streaming 响应格式
目标: 搞清楚 streamGenerateContent 返回的数据结构
"""

import os
import json
import requests

API_BASE_URL = "http://localhost:7860"
MODEL = "gemini-2.5-flash"  # 使用一个快速模型进行测试
AUTH_TOKEN = os.getenv("GEMINI_AUTH_PASSWORD", "123456")  # 默认密码

def get_headers():
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return headers

def test_non_streaming():
    """测试非流式请求 (作为对照)"""
    print("=" * 60)
    print("测试 1: 非流式请求 (generateContent)")
    print("=" * 60)
    
    endpoint = f"{API_BASE_URL}/v1beta/models/{MODEL}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Say 'Hello World' and nothing else."}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100}
    }
    
    response = requests.post(endpoint, headers=get_headers(), json=payload, timeout=60)
    
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print(f"Response Type: {type(response.text)}")
    print(f"Raw Response (first 2000 chars):\n{response.text[:2000]}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"\nParsed JSON type: {type(data)}")
            print(f"Top-level keys: {data.keys() if isinstance(data, dict) else 'N/A (list)'}")
        except Exception as e:
            print(f"JSON parse error: {e}")
    
    print()

def test_streaming_raw():
    """测试流式请求 - 原始输出"""
    print("=" * 60)
    print("测试 2: 流式请求 (streamGenerateContent) - 原始数据")
    print("=" * 60)
    
    endpoint = f"{API_BASE_URL}/v1beta/models/{MODEL}:streamGenerateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Count from 1 to 5, one number per line."}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200}
    }
    
    with requests.post(endpoint, headers=get_headers(), json=payload, stream=True, timeout=60) as response:
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print()
        
        # 收集所有 chunks
        chunks = []
        print("--- RAW CHUNKS (iter_content) ---")
        for i, chunk in enumerate(response.iter_content(chunk_size=None)):
            decoded = chunk.decode('utf-8', errors='replace')
            chunks.append(decoded)
            print(f"[Chunk {i}] Length={len(decoded)}")
            print(decoded[:500] + ("..." if len(decoded) > 500 else ""))
            print()
        
        full_response = "".join(chunks)
        print(f"\n--- FULL RESPONSE ({len(full_response)} chars) ---")
        print(full_response[:3000] + ("..." if len(full_response) > 3000 else ""))
    
    print()

def test_streaming_lines():
    """测试流式请求 - 按行解析"""
    print("=" * 60)
    print("测试 3: 流式请求 (streamGenerateContent) - 按行解析")
    print("=" * 60)
    
    endpoint = f"{API_BASE_URL}/v1beta/models/{MODEL}:streamGenerateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Write a short poem about coding."}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}
    }
    
    with requests.post(endpoint, headers=get_headers(), json=payload, stream=True, timeout=60) as response:
        print(f"Status Code: {response.status_code}")
        
        print("\n--- LINES (iter_lines) ---")
        lines = []
        for i, line in enumerate(response.iter_lines(decode_unicode=True)):
            if line:
                lines.append(line)
                print(f"[Line {i}] {line[:200]}{'...' if len(line) > 200 else ''}")
        
        print(f"\n总共 {len(lines)} 行")
        
        # 尝试解析
        print("\n--- 尝试解析每行为 JSON ---")
        for i, line in enumerate(lines):
            # 处理 SSE 格式 (data: ...)
            if line.startswith("data:"):
                line = line[5:].strip()
            
            try:
                obj = json.loads(line)
                print(f"[Line {i}] ✅ Valid JSON, type={type(obj).__name__}, keys={list(obj.keys())[:5] if isinstance(obj, dict) else 'N/A'}")
            except json.JSONDecodeError as e:
                print(f"[Line {i}] ❌ Invalid JSON: {str(e)[:50]}")
    
    print()

def test_streaming_json_direct():
    """测试直接对流式响应调用 .json()"""
    print("=" * 60)
    print("测试 4: 流式请求 - 直接调用 response.json()")
    print("=" * 60)
    
    endpoint = f"{API_BASE_URL}/v1beta/models/{MODEL}:streamGenerateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Say 'test' only."}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 50}
    }
    
    # 注意: 不加 stream=True
    response = requests.post(endpoint, headers=get_headers(), json=payload, timeout=60)
    
    print(f"Status Code: {response.status_code}")
    
    try:
        data = response.json()
        print("✅ JSON parsed successfully")
        print(f"Type: {type(data)}")
        if isinstance(data, list):
            print(f"List length: {len(data)}")
            for i, item in enumerate(data[:3]):
                print(f"  Item {i}: keys = {list(item.keys()) if isinstance(item, dict) else 'N/A'}")
        elif isinstance(data, dict):
            print(f"Keys: {list(data.keys())}")
    except Exception as e:
        print(f"❌ JSON parse failed: {e}")
        print(f"Raw text: {response.text[:1000]}")
    
    print()


if __name__ == "__main__":
    print("🧪 geminicli2api Streaming 测试")
    print()
    
    test_non_streaming()
    test_streaming_raw()
    test_streaming_lines()
    test_streaming_json_direct()
    
    print("=" * 60)
    print("测试完成!")
    print("=" * 60)
