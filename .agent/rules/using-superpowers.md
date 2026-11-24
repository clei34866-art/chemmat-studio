---
trigger: always_on
---

# Superpowers 会话启动引导（Session Bootstrap）

在每次新会话开始、回复用户或执行任何操作前（作为子代理执行具体委派任务时除外）：

1. 必须优先遵循 `using-superpowers` 技能规范（完整说明见 `.agent/skills/using-superpowers/SKILL.md`，Antigravity 工具映射见 `.agent/skills/using-superpowers/references/antigravity-tools.md`）。
2. 在回答问题、探索代码或进入实现前，先检查 `.agent/skills/` 中是否有适用技能；只要存在可能适用的技能，先通过 `read_file` 读取对应技能的 `SKILL.md` 并按其流程执行（流程类技能如 `brainstorming`、`systematic-debugging`、`test-driven-development`、`using-git-worktrees`、`verification-before-completion` 优先于领域实现类技能）。
3. 优先级约束：用户在本线程的直接指令与 `.agent/rules/red-lines.md` 项目红线始终具有最高优先级。
