# WorkBuddy 项目交接

用户约束：从 2026-09-18 开始；团队三人，每位成员总共 1000 活动 credits；同一成员的 WorkBuddy 与 CodeBuddy 按共享额度池管理，不能各算 1000；主要开发工具 WorkBuddy。
项目目录固定为 `/Users/hanweizhou/Desktop/Tribunal`。先读 WORKBUDDY-SCOPE.md；不得尝试读取项目外的同级目录。

应用设计：Python 包 `tribunal/`，先用标准库 unittest，界面采用 Streamlit（等 UI 阶段再加依赖），模型通过单一 adapter 接入。
流程：loader -> deterministic prepass/facts -> shared brief -> two advocates -> referee -> judge -> finalizer -> transcript/UI。
默认单轮两方陈述加一次判官，正常每案三次 LLM 调用。开发积分与应用推理费用分开。

案件文件的四个顶层键为 `schema_version`、`case_no`、`dispute` 和 `evidence`。四个键都必须保留；`case_no` 用于确认加载的是请求案件，`schema_version` 用于契约兼容检查。
缺失证据仍须保留 `evidence_id`；其 `payload` 为 `null`，而 `status: "MISSING"` 与 `weight_multiplier: 0.0` 位于该证据的 `admissibility` 对象内。
开发时可按 `WORKBUDDY-SCOPE.md` 读取公开契约、必要 index 和政策。传给运行时 Agent 的 bundle 只能包含所选案件的公开内容和所选政策，不得包含开发文档或答案字段。答案、语料源、历史交接和手册都不在这个工作区，不能请求或注入运行时 prompt。
金额用 Decimal；置信度阈值依政策读取；所有主张同时引用证据和条款。

实际已存在：可用案件、政策、项目说明与应用空目录；应用功能和运行时 API 尚未实现。以当前文件、实际 API 文档和测试为准。

每轮完成一个可验收模块，读限定文件，报告修改、测试、未解决问题；不自动重新生成整个项目。
记录真实工具贡献，不删改历史工具归属，不把本次 Codex 准备工作描述成 WorkBuddy 生成。
