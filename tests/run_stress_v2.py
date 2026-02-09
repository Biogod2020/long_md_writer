import asyncio
import os
import shutil
from pathlib import Path
from extreme_stress_test_patcher import extreme_stress_test

if __name__ == "__main__":
    # 我们运行 extreme_stress_test，它内部已经有 max_iterations=3 了
    # 我们只需要确保它能跑起来
    asyncio.run(extreme_stress_test())
