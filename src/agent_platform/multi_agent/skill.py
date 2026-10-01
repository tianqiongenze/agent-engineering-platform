"""BC5 · Skill 系统(阶段五):能力包注册与场景匹配。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SkillDef:
    name: str
    scenario: str  # 适用场景描述(检索匹配面)
    steps: list[str]  # 执行方法论
    version: str = "1.0.0"
    quality_bar: str = ""


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDef] = {}

    def register(self, skill: SkillDef) -> None:
        """同名注册视为升级:版本号必须更大(版本管理)。"""
        existing = self._skills.get(skill.name)
        if existing and float(skill.version) <= float(existing.version):
            raise ValueError(
                f"skill {skill.name} version must increase: {existing.version} → {skill.version}"
            )
        self._skills[skill.name] = skill

    def find(self, task_description: str) -> SkillDef | None:
        """场景匹配:任务与场景的 2-gram 重叠数最大者胜(阈值 2 过滤噪声)。"""
        best: tuple[int, SkillDef] | None = None
        task_ngrams = {task_description[i : i + 2] for i in range(len(task_description) - 1)}
        for skill in self._skills.values():
            scene_ngrams = {skill.scenario[i : i + 2] for i in range(len(skill.scenario) - 1)}
            overlap = len(scene_ngrams & task_ngrams)
            if overlap >= 2 and (best is None or overlap > best[0]):
                best = (overlap, skill)
        return best[1] if best else None
