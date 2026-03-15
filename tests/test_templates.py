"""
测试模板系统
"""

import tempfile
from datetime import datetime
from pathlib import Path

from dimcause.core.templates import TemplateManager


class TestTemplateManager:
    """测试 TemplateManager"""

    def test_builtin_templates(self):
        """测试内置模板"""
        tm = TemplateManager()
        templates = tm.list_templates()
        assert "bug-report" in templates
        assert "decision-log" in templates

    def test_render_safe(self):
        """测试渲染安全性 (避免 {} 冲突)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tm = TemplateManager(user_template_dir=tmpdir)

            # 创建包含代码块的模板
            tpl_path = Path(tmpdir) / "code-test.md"
            tpl_path.write_text(
                """
Date: {date}
Code:
```js
function test() { return {}; }
```
""",
                encoding="utf-8",
            )

            rendered = tm.render("code-test")

            today = datetime.now().strftime("%Y-%m-%d")
            assert today in rendered
            # 确保代码块中的 {} 没有被破坏或导致报错
            assert "function test() { return {}; }" in rendered

    def test_custom_context(self):
        """测试自定义变量"""
        tm = TemplateManager()

        # 使用内置 job-start 模板，它包含 {job_id}
        content = tm.render("job-start", job_id="MY-JOB-123")
        assert "MY-JOB-123" in content  # job_id 出现在模板内容中（标题已改为中文）
