# 今天从这里开始 / 2026-09-18

1. 打开 WorkBuddy 并登录你自己的账号，记录实际余额和到期时间。
2. 新建任务，将工作目录指定为 `/Users/hanweizhou/Desktop/Tribunal`。界面名称可能因版本不同；让它先回报当前目录，确认路径一致再继续。
3. 复制下面完整提示词。这是工作区验收任务；应用开发从 Loader 和政策读取开始。

```text
Today is 18 September 2026. I am participating in the Tencent Cloud AI Singapore Hackathon. The project is called Tribunal and it will be built primarily with WorkBuddy. Each team member has only 1,000 total hackathon credits, and that member's WorkBuddy and CodeBuddy usage draws from the same credit pool.
The working directory must be /Users/hanweizhou/Desktop/Tribunal. Report the actual working directory before taking any action.
Read README.md, WORKBUDDY-SCOPE.md, and WORKBUDDY-HANDOFF.md before doing anything else. Then list only the top-level directories; do not recursively scan the workspace.
Create a local Python virtual environment named .venv and install requirements.txt. Do not inspect or create any private evaluation dataset, answer key, generator, PDF, or external directory.
Write the actual directory listing and Python version to docs/notes/2026-09-18-preflight.md. State clearly that the application has not been implemented yet.
Do not call paid model APIs, implement Agents, initialize or publish a remote repository, or perform external actions.
Finally, list the files created or changed, the commands actually executed, and the real verification results. I will save a genuine screenshot of this conversation.
```

4. 检查报告后截取真实会话，保存 `docs/buddy-log/2026-09-18-hanwei-preflight.png`；记录任务前后余额。
5. 下一个 WorkBuddy 任务按 `WORKBUDDY-SCOPE.md` 只读本轮明确列出的文件；实现 Loader 前应查看无答案的 `data/PUBLIC-CONTRACT.md` 和一个明确指定的公开案件，不要凭提示词手写猜测数据结构。

此目录是本次已完成的准备工作；此处没有伪造的 WorkBuddy 截图或运行时结果。
