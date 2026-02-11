
import re
import json

content = """
:::visual {"id": "s2-fig-cardiac-cycle-loop", "action": "GENERATE_MERMAID", "reason": "总结心动周期中向量旋转与投影的动态过程，为后续章节做铺垫。", "description": "graph LR; A[窦房结启动] --> B[心房向量指向左下]; B --> C{投影到导联II}; C -->|夹角小| D[产生正向P波]; D --> E[心室除极开始]; E --> F[室间隔左向右投影]; F -->|夹角大| G[产生负向Q波]; G --> H[心 室主向量左下投影]; H -->|平行| I[产生高耸R波];"}
向量的舞蹈：心电图波形的本质是 3D 向量在 1D 轴上的逐帧投影。
:::
"""

pattern = re.compile(r':::visual\s*(\{[\s\S]*?\})([\s\S]*?):::', re.DOTALL)
matches = list(pattern.finditer(content))

print(f"Found {len(matches)} matches")
for i, match in enumerate(matches):
    print(f"Match {i+1}:")
    print(f"  Group 1 (JSON): {match.group(1)}")
    print(f"  Group 2 (Body): {match.group(2)}")
