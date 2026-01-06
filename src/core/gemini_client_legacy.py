"""
Native Gemini API Client for geminicli2api proxy.
Supports thinkingConfig and maximum reasoning budget.
"""

import os
import json
import requests
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class GeminiResponse:
    """Gemini API 响应封装"""
    text: str = ""
    thoughts: list[str] = field(default_factory=list)
    raw_response: Optional[dict] = None
    success: bool = True
    error: Optional[str] = None


class GeminiClient:
    """
    Native Gemini API 客户端
    使用 geminicli2api 代理服务器进行透传调用
    """
    
    DEFAULT_MODEL = "gemini-3-flash-preview-maxthinking"
    
    def __init__(
        self,
        api_base_url: str = "http://localhost:7860",
        auth_token: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_token = auth_token or os.getenv("GEMINI_AUTH_PASSWORD", "123456")
        self.model = model or self.DEFAULT_MODEL
        
    def _get_headers(self) -> dict:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    def _build_payload(
        self,
        prompt: Optional[str] = None,
        parts: Optional[list[dict]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_output_tokens: int = 65536,
    ) -> dict:
        """
        构建 Native Gemini 格式的请求载荷
        """
        contents = []
        
        # 系统指令（如果有）
        if system_instruction:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[SYSTEM INSTRUCTION]\n{system_instruction}\n[END SYSTEM INSTRUCTION]"}]
            })
            contents.append({
                "role": "model", 
                "parts": [{"text": "Understood. I will follow these instructions."}]
            })
        
        # 用户输入
        user_parts = []
        if prompt:
            user_parts.append({"text": prompt})
        if parts:
            user_parts.extend(parts)
            
        if not user_parts:
            # 避免空请求
            user_parts.append({"text": " "})
            
        contents.append({
            "role": "user",
            "parts": user_parts
        })
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "maxOutputTokens": max_output_tokens,
            }
        }
        
        return payload

    
    def _parse_response(self, response_json: dict) -> GeminiResponse:
        """解析 Gemini API 响应"""
        result = GeminiResponse(raw_response=response_json)
        
        try:
            candidates = response_json.get("candidates", [])
            if not candidates:
                result.success = False
                result.error = "No candidates in response"
                return result
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            text_parts = []
            thought_parts = []
            
            for part in parts:
                if part.get("thought", False):
                    # 这是思维过程
                    thought_parts.append(part.get("text", ""))
                else:
                    # 这是实际输出
                    text_parts.append(part.get("text", ""))
            
            result.text = "\n".join(text_parts)
            result.thoughts = thought_parts
            
        except Exception as e:
            result.success = False
            result.error = f"Failed to parse response: {str(e)}"
        
        return result
    
    def generate(
        self,
        prompt: Optional[str] = None,
        parts: Optional[list[dict]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_output_tokens: int = 65536,
        stream: bool = False,
    ) -> GeminiResponse:
        """
        调用 Gemini API 生成内容
        
        Args:
            prompt: 用户输入(文本)
            parts: 用户输入(多模态部件列表)
            system_instruction: 系统指令
            temperature: 温度参数
            top_p: Top-P 采样参数
            max_output_tokens: 最大输出 token 数
            stream: 是否使用流式生成 (解决长生成 500 错误)
            
        Returns:
            GeminiResponse 对象
        """
        method = "streamGenerateContent" if stream else "generateContent"
        endpoint = f"{self.api_base_url}/v1beta/models/{self.model}:{method}"
        
        payload = self._build_payload(
            prompt=prompt,
            parts=parts,
            system_instruction=system_instruction,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        
        try:
            if stream:
                # 流式处理逻辑 (SSE 格式)
                with requests.post(
                    endpoint,
                    headers=self._get_headers(),
                    json=payload,
                    stream=True,
                    timeout=300
                ) as response:
                    if response.status_code != 200:
                        return GeminiResponse(
                            success=False,
                            error=f"API Error {response.status_code}: {response.text}"
                        )
                    
                    all_text_parts = []
                    all_thought_parts = []
                    last_full_json = None
                    
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        
                        # 处理 SSE 前缀 "data: "
                        if line.startswith("data:"):
                            json_str = line[len("data:"):].strip()
                        else:
                            json_str = line.strip()
                            
                        try:
                            chunk_data = json.loads(json_str)
                            last_full_json = chunk_data # 保留最后一个完整包供 raw_response 使用
                            
                            # 解析 chunk
                            candidates = chunk_data.get("candidates", [])
                            if candidates:
                                content = candidates[0].get("content", {})
                                parts = content.get("parts", [])
                                for p in parts:
                                    if p.get("thought", False):
                                        all_thought_parts.append(p.get("text", ""))
                                    else:
                                        all_text_parts.append(p.get("text", ""))
                        except json.JSONDecodeError:
                            continue
                            
                    return GeminiResponse(
                        text="".join(all_text_parts),
                        thoughts=all_thought_parts,
                        raw_response=last_full_json,
                        success=True
                    )
            else:
                # 标准非流式逻辑
                response = requests.post(
                    endpoint,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=300
                )
                
                if response.status_code == 200:
                    return self._parse_response(response.json())
                else:
                    return GeminiResponse(
                        success=False,
                        error=f"API Error {response.status_code}: {response.text}"
                    )
                
        except requests.exceptions.Timeout:
            return GeminiResponse(success=False, error="Request timeout after 300 seconds")
        except requests.exceptions.RequestException as e:
            return GeminiResponse(success=False, error=f"Request failed: {str(e)}")
    
    def test_connection(self) -> bool:
        """测试与代理服务器的连接"""
        try:
            response = self.generate(
                prompt="Hello, respond with 'OK' only.",
                temperature=0.1,
                
            )
            return response.success and len(response.text) > 0
        except Exception:
            return False


# 便捷函数
def create_client(
    api_base_url: str = "http://localhost:7860",
    auth_token: Optional[str] = None,
) -> GeminiClient:
    """创建 Gemini 客户端实例"""
    return GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
