from typing import List

from dimcause.core.history import GitCommit
from dimcause.extractors.llm_client import LiteLLMClient


class DecisionAnalyzer:
    """
    Analyzes decision history and code evolution.
    """

    def __init__(self, client: LiteLLMClient):
        self.client = client

    def analyze_evolution(
        self, file_path: str, commits: List[GitCommit], lang: str = "zh-CN"
    ) -> str:
        """
        Generate a narrative explaining the evolution of the file.
        """
        prompt = self._build_explanation_prompt(file_path, commits, lang)
        system_msg = "You are a code historian who explains code evolution in a narrative style."

        return self.client.complete(prompt=prompt, system=system_msg)

    def _append_object_evidence(self, prompt_parts: List[str], commit: GitCommit) -> None:
        """将对象证据附加到解释 prompt 中。"""
        projection = (getattr(commit, "metadata", {}) or {}).get("object_projection")
        if not isinstance(projection, dict):
            return

        material = projection.get("material")
        if not isinstance(material, dict):
            return

        material_label = (
            material.get("title")
            or material.get("source_ref")
            or material.get("id")
            or "Unnamed Material"
        )

        prompt_parts.append("   Object Evidence:")
        prompt_parts.append(f"   - Material: {material_label}")

        claims = projection.get("claims")
        if not isinstance(claims, list) or not claims:
            return

        first_claim = claims[0]
        if not isinstance(first_claim, dict):
            return

        claim_statement = first_claim.get("statement")
        if claim_statement:
            prompt_parts.append(f"   - Claim: {claim_statement}")

    def _build_explanation_prompt(self, file_path: str, commits: List[GitCommit], lang: str) -> str:
        """Build prompt for LLM explanation"""

        # Language mapping
        lang_map = {
            "zh": "Simplified Chinese (简体中文)",
            "zh-cn": "Simplified Chinese (简体中文)",
            "zh-tw": "Traditional Chinese (繁体中文)",
            "en": "English",
            "ja": "Japanese (日本語)",
            "ko": "Korean (한국어)",
            "es": "Spanish (Español)",
            "fr": "French (Français)",
            "de": "German (Deutsch)",
            "ru": "Russian (Русский)",
        }

        target_lang_str = lang_map.get(lang.lower(), lang)
        lang_instruction = f"Write in {target_lang_str}"

        prompt_parts = [
            "# Task: Explain Code Evolution (CAUSAL CHAIN)",
            "",
            f"Analyze the evolution of `{file_path}` based on Git history and Dimcause causal events.",
            "",
            "## Timeline with CAUSAL RELATIONSHIPS:",
            "",
        ]

        for i, commit in enumerate(commits, 1):
            # Check for H2 Event Type
            evt_type = getattr(commit, "type", "git_commit")
            is_causal = getattr(commit, "from_causal_chain", False)

            if evt_type == "git_commit":
                # Standard Git Commit Format
                prompt_parts.append(f"{i}. **{commit.date}** [Code Change] - {commit.message}")
                prompt_parts.append(f"   Author: {commit.author}, Hash: {commit.hash[:8]}")
            else:
                # Context Event Format (Decision, Reasoning, etc)
                prompt_parts.append(
                    f"{i}. **{commit.date}** [{evt_type.upper()}] - {commit.message}"
                )
                prompt_parts.append(f"   Author: {commit.author} (Source: Dimcause Event)")
                if is_causal:
                    prompt_parts.append("   Causal Evidence: reached via GraphStore causal chain")

            self._append_object_evidence(prompt_parts, commit)

            # Add legacy context events (if any)
            if commit.context_events:
                prompt_parts.append("   > **Related Context:**")
                for evt in commit.context_events[:3]:
                    summary = evt.get("summary", "No summary")
                    prompt_parts.append(f"   > - [{evt.get('type', 'event').upper()}] {summary}")

            # 标记因果关系
            if i > 1:
                prompt_parts.append("   → 因果: 导致了下一步的变化")

            prompt_parts.append("")

        prompt_parts.append("## Instructions:")
        prompt_parts.append("1. 分析因果链 (CAUSAL CHAIN)：")
        prompt_parts.append("   - 识别每个事件的**原因**和**结果**")
        prompt_parts.append("   - 按时间顺序追溯：从原因 → 结果 → 影响")
        prompt_parts.append("   - 关键问题：这个代码为什么会变成这样？因为之前发生了什么？")
        prompt_parts.append(
            "   - 对显式标记为 Causal Evidence 的事件赋予更高权重，不要退回纯时间线复述"
        )
        prompt_parts.append(
            "   - 如果事件附带 Object Evidence，必须显式使用 Material 与 Claim 解释证据从何而来"
        )
        prompt_parts.append("")
        prompt_parts.append("2. 生成连贯的叙述 (narrative)：")
        prompt_parts.append("   - 解释文件的整体演化和目的")
        prompt_parts.append("   - 强调关键决策点和转折点")
        prompt_parts.append("   - 将代码变更与动机连接")
        prompt_parts.append("")
        prompt_parts.append("3. 使用讲故事风格，避免简单罗列")
        prompt_parts.append(f"4. {lang_instruction}")
        prompt_parts.append("5. 简洁但有深度 (300-500 words)")

        return "\n".join(prompt_parts)
