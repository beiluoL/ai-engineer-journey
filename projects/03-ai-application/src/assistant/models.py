"""示例数据模型：结构化输出要「什么形状」（对应 milestones/03）。

用 Pydantic 而不是裸 dict 的三个好处：
    1. 能生成 JSON Schema 发给模型
    2. 模型输出后能立刻校验（类型、范围、枚举）
    3. 拿到的是有 IDE 补全的对象，不是 dict["xxx"]
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillExtraction(BaseModel):
    """从一段自我介绍里抽取的技能信息。"""

    name: str = Field(description="候选人姓名")
    skills: list[str] = Field(description="技能列表，用标准英文原名，如 Java / Spring Boot")
    years: int = Field(description="工作年限", ge=0, le=40)
    summary: str = Field(description="一句话总结，不超过 50 字", max_length=80)


class InterviewQuestion(BaseModel):
    """一道面试题。"""

    question: str = Field(description="题目正文，不超过 40 字")
    difficulty: str = Field(description="难度", pattern="^(easy|medium|hard)$")


class QuestionSet(BaseModel):
    """一组面试题。"""

    topic: str = Field(description="考察的知识点")
    questions: list[InterviewQuestion] = Field(description="题目列表", min_length=1, max_length=5)


# 供 /chat/structured 的 schema 参数选择
REGISTRY: dict[str, type[BaseModel]] = {
    "skill": SkillExtraction,
    "interview": QuestionSet,
}
