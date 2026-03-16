"""
pytest 全局配置

在所有测试开始前设置环境变量，阻止 HuggingFace Hub 联网检查。
transformers tokenizer (XLMRobertaTokenizer) 即使 local_files_only=True 也会
在初始化时调用 is_base_mistral() → model_info() → HF Hub API。
HF_HUB_OFFLINE=1 可完全阻断该行为。
"""

import os
import sys
from pathlib import Path

# 公开导出仓库默认不依赖 editable install，这里显式注入 src 布局路径。
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# 必须在 transformers 等库导入前设置，确保所有测试进程都不联网访问 HF Hub
os.environ.setdefault("HF_HUB_OFFLINE", "1")
