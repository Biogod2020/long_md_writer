
import os
import json
import httpx
import asyncio
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass, field

@dataclass
class GeminiResponse:
    """Wrapper for Gemini API Response"""
    text: str = ""
    json_data: Optional[Dict] = None
    success: bool = True
    error: Optional[str] = None
    raw_response: Optional[Dict] = None
    thoughts: List[str] = field(default_factory=list)

class GeminiClient:
    """
    Async Gemini API Client targeting the geminicli2api proxy (v1/chat/completions).
    Supports structured output (JSON Schema) and high concurrency.
    """
    
    DEFAULT_MODEL = "gemini-3-flash-preview-maxthinking"
    DEFAULT_BASE_URL = "http://localhost:8888/v1"
    
    def __init__(
        self,
        api_base_url: str = DEFAULT_BASE_URL,
        auth_token: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_token = auth_token or os.getenv("GEMINI_AUTH_PASSWORD", "123456")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        
    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def generate_async(
        self,
        prompt: Optional[Union[str, List[Dict[str, Any]]]] = None,
        parts: Optional[List[Dict]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 65536,
        model: Optional[str] = None,
        **kwargs
    ) -> GeminiResponse:
        """
        Standard async text/multimodal generation.
        Converts Gemini 'parts' to OpenAI 'content' array if needed.
        """
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        
        user_content = []
        
        # Accept a list prompt as multimodal parts (backward compatibility)
        if isinstance(prompt, list):
            if parts:
                parts = parts + prompt
            else:
                parts = prompt
            prompt = None

        # Handle simple string prompt
        if prompt:
            user_content.append({"type": "text", "text": prompt})
            
        # Handle Gemini-style parts
        if parts:
            for part in parts:
                if "text" in part:
                    user_content.append({"type": "text", "text": part["text"]})
                elif "inlineData" in part or "inline_data" in part:
                    inline = part.get("inlineData") or part.get("inline_data") or {}
                    mime = inline.get("mimeType") or inline.get("mime_type") or "image/jpeg"
                    data = inline.get("data")
                    if not data:
                        continue
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{data}"
                        }
                    })
        
        # If user_content is simple (just one text), send as string (optional optimization, but OpenAI handles list fine)
        if len(user_content) == 1 and user_content[0]["type"] == "text":
             messages.append({"role": "user", "content": user_content[0]["text"]})
        elif user_content:
             messages.append({"role": "user", "content": user_content})
        else:
             # Empty prompt guard
             messages.append({"role": "user", "content": " "})
        
        is_streaming = kwargs.get("stream", False)
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens, 
            "stream": is_streaming
        }
        
        url = f"{self.api_base_url}/chat/completions"
        
        # Debug: Save last payload to a file
        try:
            with open("last_request_payload.json", "w", encoding="utf-8") as f:
                json.dump({"url": url, "payload": payload}, f, indent=2, ensure_ascii=False)
        except:
            pass
            
        try:
            # Use longer timeout for potentially slow responses
            client_timeout = httpx.Timeout(self.timeout, connect=10.0)
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                if is_streaming:
                    full_content = []
                    full_thoughts = []
                    
                    final_error = None
                    async with client.stream("POST", url, json=payload, headers=self._get_headers()) as resp:
                        if resp.status_code != 200:
                            error_body = await resp.aread()
                            return GeminiResponse(success=False, error=f"HTTP {resp.status_code}: {error_body.decode()}")
                        
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    
                                    # Handle errors sent inside the stream
                                    if "error" in chunk:
                                        final_error = f"Stream Error: {chunk['error'].get('message', 'Unknown error')}"
                                        print(f"\n[Stream Error] {final_error}")
                                        break
                                        
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    
                                    # Capture normal content
                                    content = delta.get("content", "")
                                    if content:
                                        full_content.append(content)
                                        if self.api_base_url.find("localhost") != -1:
                                            print(content, end="", flush=True)
                                            
                                    # Capture reasoning/thoughts
                                    reasoning = delta.get("reasoning_content", "")
                                    if reasoning:
                                        full_thoughts.append(reasoning)
                                except Exception as e:
                                    if self.api_base_url.find("localhost") != -1:
                                        print(f"\n[Stream Error Parsing] {e} on line: {line}")
                                    pass
                    
                    final_text = "".join(full_content)
                    final_thoughts = "".join(full_thoughts)
                    
                    if final_error and not final_text:
                         return GeminiResponse(success=False, error=final_error)
                         
                    if not final_text:
                        if not final_thoughts:
                            print(f"\n[Stream Warning] No content or thoughts captured from stream.")
                        else:
                            print(f"\n[Stream Note] Only thoughts captured ({len(final_thoughts)} chars).")
                            
                    return GeminiResponse(text=final_text, thoughts=full_thoughts, success=True)
                else:
                    resp = await client.post(url, json=payload, headers=self._get_headers())
                    
                    if resp.status_code != 200:
                        return GeminiResponse(success=False, error=f"HTTP {resp.status_code}: {resp.text}")
                    
                    data = resp.json()
                    try:
                        message = data["choices"][0]["message"]
                        content = message.get("content", "")
                        thoughts = message.get("reasoning_content", "")
                        full_thoughts = [thoughts] if thoughts else []
                        return GeminiResponse(text=content, thoughts=full_thoughts, raw_response=data, success=True)
                    except (KeyError, IndexError) as e:
                        # Missing expected fields in response
                        return GeminiResponse(success=False, error=f"Malformed response: {e}. Data: {str(data)[:500]}")
                
        except Exception as e:
            return GeminiResponse(success=False, error=str(e))

    async def generate_structured_async(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        schema_name: str = "output",
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        model: Optional[str] = None
    ) -> GeminiResponse:
        """
        Generate strict JSON output adhering to a JSON Schema.
        """
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": response_schema
                }
            }
        }
        
        url = f"{self.api_base_url}/chat/completions"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=self._get_headers())
                
                if resp.status_code != 200:
                    return GeminiResponse(success=False, error=f"HTTP {resp.status_code}: {resp.text}")
                
                data = resp.json()
                content_str = data["choices"][0]["message"]["content"]
                
                try:
                    json_data = json.loads(content_str)
                    return GeminiResponse(text=content_str, json_data=json_data, raw_response=data, success=True)
                except json.JSONDecodeError:
                    return GeminiResponse(success=False, error="Failed to parse returned JSON string", text=content_str)
                    
        except Exception as e:
            return GeminiResponse(success=False, error=str(e))

    async def generate_parallel_async(self, tasks: List[Dict], debug: bool = False) -> List[GeminiResponse]:
        """
        Execute multiple generation tasks in parallel with retry logic.
        Each task dict should contain args for generate_async or generate_structured_async.
        
        Example task:
        {
            "type": "text", # or "structured"
            "prompt": "...",
            "system_instruction": "...",
            ... args ...
        }
        """
        max_concurrent = 2  # Conservative limit to avoid rate limiting
        semaphore = asyncio.Semaphore(max_concurrent)
        max_retries = 5
        base_delay = 1.0
        
        async with httpx.AsyncClient(timeout=self.timeout, limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)) as client:
            
            async def worker(task_idx: int, task: dict):
                async with semaphore:
                    task_type = task.get("type", "text")
                    task_id = task.get("issue_id", f"task-{task_idx}")
                    t_args = task.copy()
                    if "type" in t_args: del t_args["type"]
                    if "issue_id" in t_args: del t_args["issue_id"]
                    if "target_file" in t_args: del t_args["target_file"]
                    
                    url = f"{self.api_base_url}/chat/completions"
                    headers = self._get_headers()
                    
                    # Construct Payload based on type
                    if task_type == "structured":
                        messages = []
                        if t_args.get("system_instruction"):
                             messages.append({"role": "system", "content": t_args.pop("system_instruction")})
                        messages.append({"role": "user", "content": t_args.pop("prompt")})
                        
                        schema = t_args.pop("response_schema")
                        name = t_args.pop("schema_name", "output")
                        
                        payload = {
                            "model": t_args.get("model", self.model),
                            "messages": messages,
                            "temperature": t_args.get("temperature", 0.1),
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {"name": name, "schema": schema}
                            }
                        }
                    else: # text
                        messages = []
                        if t_args.get("system_instruction"):
                             messages.append({"role": "system", "content": t_args.pop("system_instruction")})
                        messages.append({"role": "user", "content": t_args.pop("prompt")})
                        
                        payload = {
                            "model": t_args.get("model", self.model),
                            "messages": messages,
                            "temperature": t_args.get("temperature", 0.7),
                            "max_completion_tokens": t_args.get("max_tokens", 65536)
                        }

                    # Retry loop with exponential backoff
                    for attempt in range(max_retries):
                        try:
                            if debug:
                                print(f"      [Worker {task_id}] Attempt {attempt+1}/{max_retries}...")
                            
                            resp = await client.post(url, json=payload, headers=headers)
                            
                            # Handle retryable errors (429, 5xx)
                            if resp.status_code in [429, 502, 503, 504] and attempt < max_retries - 1:
                                delay = base_delay * (1.5 ** attempt)
                                if resp.status_code == 429:
                                    # Try to extract retry delay from response
                                    try:
                                        error_data = resp.json()
                                        for detail in error_data.get("error", {}).get("details", []):
                                            if "retryDelay" in detail:
                                                delay = float(str(detail["retryDelay"]).rstrip('s'))
                                                break
                                    except:
                                        pass
                                if debug:
                                    print(f"      [Worker {task_id}] Rate limited ({resp.status_code}), retrying in {delay:.1f}s...")
                                await asyncio.sleep(delay)
                                continue
                            
                            if resp.status_code != 200:
                                error_body = resp.text[:200] if resp.text else ""
                                return GeminiResponse(success=False, error=f"HTTP {resp.status_code}: {error_body}")
                            
                            data = resp.json()
                            
                            # Validate response structure
                            if not data.get("choices") or len(data["choices"]) == 0:
                                return GeminiResponse(success=False, error="Empty choices in API response")
                            
                            content = data["choices"][0].get("message", {}).get("content", "")
                            if not content:
                                return GeminiResponse(success=False, error="Empty content in API response")
                            
                            if debug:
                                # Print first 200 chars of response for debugging
                                preview = content[:200].replace('\n', ' ')
                                print(f"      [Worker {task_id}] ✓ Response received: {preview}...")
                            
                            if task_type == "structured":
                                return GeminiResponse(text=content, json_data=json.loads(content), success=True)
                            else:
                                return GeminiResponse(text=content, success=True)
                                
                        except httpx.RequestError as e:
                            if attempt < max_retries - 1:
                                delay = base_delay * (1.5 ** attempt)
                                if debug:
                                    print(f"      [Worker {task_id}] Connection error: {e}, retrying in {delay:.1f}s...")
                                await asyncio.sleep(delay)
                                continue
                            return GeminiResponse(success=False, error=f"Connection error after {max_retries} attempts: {str(e)}")
                        except Exception as e:
                            return GeminiResponse(success=False, error=f"Exception: {str(e)}")
                    
                    return GeminiResponse(success=False, error=f"Failed after {max_retries} attempts")

            coroutines = [worker(i, task) for i, task in enumerate(tasks)]
            return await asyncio.gather(*coroutines)

    # Synchronous Wrappers for Compatibility
    def generate(self, *args, **kwargs) -> GeminiResponse:
        return asyncio.run(self.generate_async(*args, **kwargs))

    def generate_structured(self, *args, **kwargs) -> GeminiResponse:
        return asyncio.run(self.generate_structured_async(*args, **kwargs))
    
    def generate_parallel(self, tasks: List[Dict], debug: bool = False) -> List[GeminiResponse]:
         return asyncio.run(self.generate_parallel_async(tasks, debug=debug))
