import os
import json
import httpx
import asyncio
import re
from typing import Optional, Dict, List
from dataclasses import dataclass

@dataclass
class GeminiResponse:
    """Wrapper for Native Gemini API Response"""
    text: str = ""
    json_data: Optional[Dict] = None
    success: bool = True
    error: Optional[str] = None
    raw_response: Optional[Dict] = None
    thoughts: str = ""

class GeminiClient:
    """
    Native Gemini API Client targeting the geminicli2api proxy (/v1beta/models/...).
    Uses Google's native JSON structure for maximum stability and feature support.
    """
    
    DEFAULT_MODEL = "gemini-3-flash-preview-maxthinking"
    DEFAULT_BASE_URL = "http://localhost:8888" # Proxy root
    
    _client: Optional[httpx.AsyncClient] = None

    def __init__(
        self,
        api_base_url: str = DEFAULT_BASE_URL,
        auth_token: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 180.0
    ):
        self.api_base_url = api_base_url.rstrip("/")
        # Auto-strip /v1 if present to target native endpoint
        if self.api_base_url.endswith("/v1"):
            self.api_base_url = self.api_base_url[:-3]
            
        self.auth_token = auth_token or os.getenv("GEMINI_AUTH_PASSWORD", "123456")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        
    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a shared httpx.AsyncClient"""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=5, 
                max_connections=20,
                keepalive_expiry=5.0
            )
            timeout = httpx.Timeout(self.timeout, connect=10.0, read=self.timeout)
            self._client = httpx.AsyncClient(
                timeout=timeout, 
                limits=limits, 
                http1=True, 
                http2=False
            )
        return self._client

    async def reset_client(self):
        """Force close and recreate the client."""
        if self._client:
            try:
                await self._client.aclose()
            except:
                pass
        self._client = None

    async def close_async(self):
        """Close the persistent client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_native_contents(self, prompt: Optional[str], parts: Optional[List[Dict]]) -> List[Dict]:
        """Translates mixed input into Native Gemini contents structure."""
        native_parts = []
        if prompt:
            native_parts.append({"text": prompt})
        
        if parts:
            for p in parts:
                if "text" in p:
                    native_parts.append({"text": p["text"]})
                elif "inline_data" in p or "inlineData" in p:
                    data_obj = p.get("inline_data") or p.get("inlineData")
                    native_parts.append({"inline_data": data_obj})
        
        return [{"role": "user", "parts": native_parts}]

    async def generate_async(
        self,
        prompt: Optional[str] = None,
        parts: Optional[List[Dict]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 65536,
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> GeminiResponse:
        """Native async generation with enhanced resilience."""
        target_model = model or self.model
        action = "streamGenerateContent" if stream else "generateContent"
        url = f"{self.api_base_url}/v1beta/models/{target_model}:{action}"
        if stream:
            url += "?alt=sse"

        payload = {
            "contents": self._build_native_contents(prompt, parts),
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        if "generation_config" in kwargs:
            payload["generationConfig"].update(kwargs["generation_config"])

        max_retries = 3
        for attempt in range(max_retries):
            try:
                client = await self._get_client()
                if stream:
                    return await self._handle_native_stream(client, url, payload)
                else:
                    resp = await client.post(url, json=payload, headers=self._get_headers())
                    if resp.status_code != 200:
                        if attempt < max_retries - 1 and resp.status_code in [500, 502, 503, 504]:
                            await asyncio.sleep(1 * (attempt + 1))
                            continue
                        return GeminiResponse(success=False, error=f"HTTP {resp.status_code}: {resp.text}")
                    
                    # Capture full details for debugging
                    result = self._parse_native_response(resp.json())
                    
                    return result
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                if attempt < max_retries - 1:
                    print(f"  [GeminiClient] ⚠️ Connection error ({type(e).__name__}). Resetting pool and retrying...")
                    await self.reset_client()
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return GeminiResponse(success=False, error=str(e))
            except httpx.ReadTimeout as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return GeminiResponse(success=False, error=str(e))
            except Exception as e:
                return GeminiResponse(success=False, error=str(e))

    def _parse_native_response(self, data: Dict) -> GeminiResponse:
        """Parses Google Native API response format."""
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                return GeminiResponse(success=False, error="No candidates in response", raw_response=data)
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            text_parts = []
            thought_parts = []
            
            for p in parts:
                if p.get("thought"):
                    thought_parts.append(p.get("text", ""))
                elif "text" in p:
                    text_parts.append(p["text"])
            
            final_text = "".join(text_parts)
            final_thoughts = "".join(thought_parts)
            
            json_data = None
            clean_text = final_text.strip()
            if clean_text:
                if "```" in clean_text:
                    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', clean_text)
                    if match:
                        clean_text = match.group(1).strip()
                
                start_obj = clean_text.find('{')
                start_arr = clean_text.find('[')
                start = -1
                if start_obj != -1 and start_arr != -1: start = min(start_obj, start_arr)
                elif start_obj != -1: start = start_obj
                elif start_arr != -1: start = start_arr
                
                if start != -1:
                    end_obj = clean_text.rfind('}')
                    end_arr = clean_text.rfind(']')
                    end = max(end_obj, end_arr)
                    if end > start:
                        try:
                            json_data = json.loads(clean_text[start:end+1])
                        except:
                            pass

            return GeminiResponse(
                text=final_text, 
                thoughts=final_thoughts, 
                json_data=json_data, 
                raw_response=data, 
                success=True
            )
        except Exception as e:
            return GeminiResponse(success=False, error=f"Parse failed: {e}", raw_response=data)

    async def _handle_native_stream(self, client, url, payload) -> GeminiResponse:
        """Handles Server-Sent Events for native stream."""
        full_text = []
        full_thoughts = []
        last_data = None
        
        try:
            async with client.stream("POST", url, json=payload, headers=self._get_headers()) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    return GeminiResponse(success=False, error=f"HTTP {resp.status_code}: {err_body.decode()}")
                
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]": break
                        try:
                            chunk = json.loads(data_str)
                            last_data = chunk
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    if p.get("thought"):
                                        full_thoughts.append(p.get("text", ""))
                                    elif "text" in p:
                                        full_text.append(p["text"])
                        except:
                            continue
            
            return GeminiResponse(
                text="".join(full_text),
                thoughts="".join(full_thoughts),
                success=True,
                raw_response=last_data
            )
        except Exception as e:
            return GeminiResponse(success=False, error=str(e))

    def test_connection(self) -> bool:
        """Simple health check via native endpoint."""
        try:
            resp = self.generate(prompt="Hello, reply 'OK'", temperature=0.1)
            return resp.success and len(resp.text) > 0
        except:
            return False

    def generate(self, *args, **kwargs) -> GeminiResponse:
        """Synchronous wrapper for generate_async with loop detection."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # SOTA: If already in a loop, we must run in a separate thread to avoid nesting
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(lambda: asyncio.run(self.generate_async(*args, **kwargs))).result()
            else:
                return loop.run_until_complete(self.generate_async(*args, **kwargs))
        except RuntimeError:
            # No event loop in this thread
            return asyncio.run(self.generate_async(*args, **kwargs))

    async def generate_structured_async(self, prompt, response_schema, **kwargs) -> GeminiResponse:
        """Uses native JSON mode."""
        kwargs["generation_config"] = kwargs.get("generation_config", {})
        kwargs["generation_config"].update({
            "response_mime_type": "application/json",
            "response_schema": response_schema
        })
        return await self.generate_async(prompt=prompt, **kwargs)

    def generate_structured(self, *args, **kwargs) -> GeminiResponse:
        """Synchronous wrapper for generate_structured_async with loop detection."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(lambda: asyncio.run(self.generate_structured_async(*args, **kwargs))).result()
            else:
                return loop.run_until_complete(self.generate_structured_async(*args, **kwargs))
        except RuntimeError:
            return asyncio.run(self.generate_structured_async(*args, **kwargs))

    async def generate_parallel_async(self, tasks: List[Dict], debug: bool = False) -> List[GeminiResponse]:
        """Execute multiple native tasks in parallel."""
        max_concurrent = 4 
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def worker(task):
            async with semaphore:
                t_prompt = task.get("prompt")
                t_parts = task.get("parts")
                t_sys = task.get("system_instruction")
                t_args = {k:v for k,v in task.items() if k not in ["prompt", "parts", "system_instruction", "issue_id", "target_file", "type"]}
                return await self.generate_async(prompt=t_prompt, parts=t_parts, system_instruction=t_sys, **t_args)

        return await asyncio.gather(*(worker(t) for t in tasks))

    def generate_parallel(self, tasks: List[Dict], debug: bool = False) -> List[GeminiResponse]:
        return asyncio.run(self.generate_parallel_async(tasks, debug))
