import os
import json
import httpx
import asyncio
import re
import random
from typing import Optional, Dict, List, Union
from dataclasses import dataclass

from .config import DEFAULT_MODEL, DEFAULT_BASE_URL, DEFAULT_AUTH_PASSWORD, DEFAULT_THINKING_LEVEL, DEFAULT_PROVIDERS

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
    Native Gemini API Client targeting standard proxies or direct API (/v1beta/models/...).
    Uses Google's native JSON structure for maximum stability and feature support.
    """
    
    _client: Optional[httpx.AsyncClient] = None

    def __init__(
        self,
        api_base_url: str = DEFAULT_BASE_URL,
        auth_token: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 180.0,
        model_provider: Optional[Union[str, List[str]]] = None
    ):
        self.api_base_url = api_base_url.rstrip("/")
        # Auto-strip /v1 if present to target native endpoint
        if self.api_base_url.endswith("/v1"):
            self.api_base_url = self.api_base_url[:-3]
            
        self.auth_token = auth_token or DEFAULT_AUTH_PASSWORD
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout
        
        # SOTA 2.1: Multi-Provider Polling Support
        if model_provider is None:
            model_provider = DEFAULT_PROVIDERS
            
        if isinstance(model_provider, list):
            self.model_providers = model_provider
        elif model_provider:
            self.model_providers = [model_provider]
        else:
            self.model_providers = []
        self._provider_index = 0
        
    def _get_next_provider(self) -> Optional[str]:
        if not self.model_providers:
            return None
        provider = self.model_providers[self._provider_index % len(self.model_providers)]
        self._provider_index += 1
        return provider

    def _get_headers(self, model_provider: Optional[str] = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        # Priority: explicit override > default (if set)
        provider = model_provider
        if provider:
            headers["Model-Provider"] = provider
        return headers

    _client: Optional[httpx.AsyncClient] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a shared httpx.AsyncClient with loop validation."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # SOTA 2.1: Loop alignment protection
        if GeminiClient._client is not None:
            if GeminiClient._loop != current_loop or GeminiClient._client.is_closed:
                # Loop mismatch or closed - must reset
                try:
                    await GeminiClient._client.aclose()
                except: pass
                GeminiClient._client = None

        if GeminiClient._client is None:
            limits = httpx.Limits(
                max_keepalive_connections=5, 
                max_connections=20,
                keepalive_expiry=5.0
            )
            timeout = httpx.Timeout(self.timeout, connect=10.0, read=self.timeout)
            
            # SOTA 2.1: Local Proxy Protection
            proxies = None
            if "localhost" in self.api_base_url or "127.0.0.1" in self.api_base_url:
                proxies = {} # Empty dict disables all proxies in httpx
                
            GeminiClient._client = httpx.AsyncClient(
                timeout=timeout, 
                limits=limits, 
                http1=True, 
                http2=False,
                proxy=proxies 
            )
            GeminiClient._loop = current_loop
            
        return GeminiClient._client

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
        thinking_level: Optional[str] = None,
        model_provider: Optional[str] = None,
        **kwargs
    ) -> GeminiResponse:
        """Native async generation with official Google thinking support."""
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
        
        # Official Thinking Configuration (Gemini 3+)
        # SOTA: thinkingLevel is the standardized way to control reasoning.
        is_gemini_3 = "gemini-3" in target_model or "gemini3" in target_model
        
        # Default to HIGH for Gemini 3 models unless specified
        t_level = thinking_level or kwargs.get("thinking_level")
        if not t_level and is_gemini_3:
            t_level = DEFAULT_THINKING_LEVEL

        if t_level:
            payload["generationConfig"]["thinkingConfig"] = {
                "includeThoughts": True,
                "thinkingLevel": t_level.upper()
            }
            # SOTA: Thinking models REQUIRE responseModalities: ["TEXT"] 
            # unless tools are present (which causes 400).
            if "tools" not in kwargs:
                payload["generationConfig"]["responseModalities"] = ["TEXT"]

        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        if "generation_config" in kwargs:
            payload["generationConfig"].update(kwargs["generation_config"])

        max_retries = 10 # SOTA 2.1: Increased from 5 to handle heavy thinking model load
        for attempt in range(max_retries):
            # SOTA 2.1: Dynamic Provider Selection
            current_provider = self._get_next_provider()
            
            try:
                client = await self._get_client()
                if stream:
                    resp = await self._handle_native_stream(client, url, payload, model_provider=current_provider)
                else:
                    http_resp = await client.post(url, json=payload, headers=self._get_headers(model_provider=current_provider))
                    if http_resp.status_code != 200:
                        # Convert to common failure for unified retry logic
                        raise httpx.HTTPStatusError(f"HTTP {http_resp.status_code}", request=None, response=http_resp)
                    resp = self._parse_native_response(http_resp.json())
                
                # SOTA: If the response indicates failure but we have retries left, treat as retryable
                if not resp.success and attempt < max_retries - 1:
                    # Check for typical retryable strings or codes
                    err_msg = str(resp.error).lower()
                    if any(x in err_msg for x in ["timeout", "500", "502", "503", "504", "429", "no healthy provider"]):
                        wait_time = (1.5 ** attempt) + random.random()
                        print(f"  [GeminiClient] ⚠️ Provider '{current_provider}' failed: {resp.error}. Retrying with next in {wait_time:.2f}s...")
                        await asyncio.sleep(wait_time)
                        continue
                
                return resp

            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError, httpx.ConnectError, httpx.HTTPStatusError, httpx.ReadTimeout) as e:
                if attempt < max_retries - 1:
                    # If it's a status error, extract the code
                    status_code = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else "Timeout/Proto"
                    wait_time = (1.2 ** attempt) + random.random()
                    print(f"  [GeminiClient] ⚠️ Attempt {attempt+1} failed ({status_code}) via '{current_provider}': {e}. Switching provider...")
                    if isinstance(e, (httpx.RemoteProtocolError, httpx.ConnectError)):
                        await self.reset_client()
                    await asyncio.sleep(wait_time)
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

    async def _handle_native_stream(self, client, url, payload, model_provider: Optional[str] = None) -> GeminiResponse:
        """Handles Server-Sent Events for native stream with enhanced robustness."""
        full_text = []
        full_thoughts = []
        last_data = None
        
        try:
            # SOTA: Increase read timeout specifically for streaming to handle thinking latency
            async with client.stream("POST", url, json=payload, headers=self._get_headers(model_provider=model_provider), timeout=httpx.Timeout(self.timeout, read=300.0)) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    return GeminiResponse(success=False, error=f"HTTP {resp.status_code}: {err_body.decode()}")
                
                async for line in resp.aiter_lines():
                    if not line: continue
                    
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
                        except Exception as e:
                            # Skip malformed chunks but continue the stream
                            if self.api_base_url.startswith("http://localhost"):
                                print(f"  [GeminiClient] ⚠️ Stream Chunk Parse Error: {e}")
                            continue
            
            return GeminiResponse(
                text="".join(full_text),
                thoughts="".join(full_thoughts),
                success=True,
                raw_response=last_data
            )
        except httpx.ReadTimeout:
            return GeminiResponse(success=False, error="Stream Read Timeout (Server taking too long to think)")
        except Exception as e:
            return GeminiResponse(success=False, error=f"Stream Error: {str(e)}")

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
        max_concurrent = 5 
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
