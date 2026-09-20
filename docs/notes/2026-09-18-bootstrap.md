# 2026-09-18 新项目准备记录

执行工具：Codex。此记录不是 WorkBuddy 使用证明。

已新建 `/Users/hanweizhou/Desktop/Tribunal`，复制原 Tencent 目录的公开 data、policy 和 requirements.txt。
原资料与原仓库保留；没有复制 .git、.claude 或旧手册到正式项目。

准备期间曾创建隔离环境并运行私有校验工具；随后已将该环境、校验工具、答案和历史材料全部移到项目外的 `Tribunal-private-eval`。正式 WorkBuddy 项目内不含 `.venv`、`tools/` 或 `data/answers/`。
在私有评测目录实际运行校验：21/21 通过，0 SKIP。
数据规模：29 disputes / 204 artifacts / 24 policy clauses。

应用目录当前为空，尚未生成业务代码、真实模型运行或 WorkBuddy 截图。
下一步：用户在 WorkBuddy 打开此目录，执行 START-HERE.md 中的第一段任务。
