# Legacy Proxy (3000 Port) Adaptation Logic Archive

This document preserves the specialized logic implemented in `GeminiClient` to handle the limitations and behaviors of the `AIClient-2-API` (3000 port) proxy. These snippets were removed during the migration to `geminicli2api-async` (8888 port).

## 1. X-Skip-Context & Extra Headers
To prevent the proxy from accumulating "Stale Request Contexts" during high-concurrency fulfillment, we injected a custom header.

### Snippet: Constructor Support
```python
def __init__(..., extra_headers: Optional[Dict[str, str]] = None):
    self.extra_headers = extra_headers or {}
```

### Snippet: Header Injection
```python
def _get_headers(self, model_provider: Optional[str] = None) -> dict:
    headers = {"Content-Type": "application/json"}
    # ...
    if self.extra_headers:
        headers.update(self.extra_headers)
    # ...
```

## 2. Rotate-First 429 Logic
The 3000 port proxy often locked accounts after a single 429. We implemented aggressive client-side rotation to bypass this.

### Snippet: Immediate Rotation
```python
# SOTA 2.1: 429 'Rotate-First' Logic
if "429" in err_msg or "resource_exhausted" in err_msg:
    reset_s = extract_reset_time(err_msg) or 30
    
    if len(self.model_providers) > 1:
        old_p = current_provider
        current_provider = self._get_next_provider()
        if current_provider == old_p:
            await asyncio.sleep(reset_s + 2)
        else:
            # Immediate retry with new provider
            continue
```

## 3. Shared Global Provider Index
To ensure uniform load balancing across multiple `GeminiClient` instances, we shared the rotation index at the class level.

### Snippet: Class-Level Index
```python
class GeminiClient:
    _global_provider_index: int = 0
    
    def _get_next_provider(self) -> Optional[str]:
        idx = (GeminiClient._global_provider_index + self._local_index_offset) % len(self.model_providers)
        GeminiClient._global_provider_index += 1
        return provider
```

## 4. Forced Zero-Keepalive
To force physical socket cleanup at the proxy layer.

### Snippet: Limits Config
```python
limits = httpx.Limits(
    max_keepalive_connections=0, 
    max_connections=20,
    keepalive_expiry=0.0
)
```
