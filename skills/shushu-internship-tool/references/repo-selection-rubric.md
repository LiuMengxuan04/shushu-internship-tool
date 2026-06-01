# Repo Selection Rubric

用这个 rubric 选择 2-3 个候选 GitHub 项目，并推荐一个主项目和一个备选项目。

## 评分维度

| 维度 | 高分信号 | 风险信号 |
| --- | --- | --- |
| JD 匹配 | README/代码直接覆盖 JD 技术词和岗位任务 | 只沾边一个热门词，无法解释岗位关联 |
| 上手速度 | 有 install、demo、测试、seed data、Docker 或清楚运行命令 | README 过期、依赖缺失、issue 大量报错 |
| 简历标题 | 一句话能变成岗位相关项目名 | 需要解释半天才看出和岗位有关 |
| 运行资源 | 本地、Docker、轻量云服务器、免费云服务或单卡可推进 | 需要复杂账号、多机多卡或巨大私有数据 |
| 维护活跃度 | 近一年有 commit 或 issue 互动 | 多年未维护且依赖老旧 |
| 学习价值 | 请求流、数据流、状态流、任务流、模型流或部署流可讲清 | 只是 UI 包装或脚本拼接 |
| 魔改空间 | 能做 API、页面、数据库、缓存、测试、部署、数据、模型或 demo 增量 | 改动只能换 README 或参数名 |
| 面试抗压 | 容易准备核心代码讲解和追问答案 | 面试官追问 input/output 就讲不下去 |
| 用户偏好匹配 | 能用 `taste_tags` / `project_taste_notes` 解释为什么符合用户选择的方向、项目形态、运行深度或面试风格 | 只迎合 taste 但 JD 弱匹配、不可运行、资源过重，或命中用户避雷项 |


## 用户偏好 / taste 规则

- 用户偏好匹配是额外小权重，只用于辅助近分候选排序和解释，不覆盖 JD 匹配、可运行性、资源成本、风险和面试抗压。
- 如果用户在 JD 后 taste gate 选择“没有 / no”，不要为了 taste 改写候选项目，也不要在后续推荐阶段重复追问。
- 如果用户选择“有 / yes”并完成结构化偏好选择或自定义输入，候选 JSON 尽量补充：
  - `taste_tags`：项目能匹配的偏好标签，例如 `backend`、`ai-app`、`local-docker`、`interview-friendly`。
  - `project_taste_notes`：候选项目通用 taste 说明，只做人类可读解释，不参与脚本打分。
  - `avoid_tags`：项目自身可能让部分用户避雷的属性，例如 `pure-frontend`、`multi-gpu`、`cloud-only`、`large-dataset`。
- 有效 taste 必须写入 `taste.json` 并传给 `candidate_score --taste`；最终表格应出现 Taste Fit，JSON 应出现 `score_breakdown.user_preference`。
- “不要 / 不想 / 避免 / 不希望”这类表达必须作为避雷项处理，不能当成正向偏好。
- 命中用户 taste 的项目仍需满足硬性条件；明显不可运行、高风险、资源超预算或 JD 牵强的项目不能只靠 taste 成为主项目。
- `candidate_score` 不从自由文本里猜分；候选 JSON 需要由 agent 显式写入 `matched_jd_terms` / `jd_match_score`、`license_score`、`runnable_score`、`resource_fit_score`。

## 淘汰条件

- 需要不可获得的私有数据、私有 checkpoint 或闭源服务。
- 最小复现明显超出用户时间和硬件预算。
- 代码主体不可读，只有 notebook 输出或二进制文件。
- 项目方向和 JD 只能靠牵强话术连接。

## 岗位族提示

- 后端：优先找有 API、数据库、缓存、鉴权、消息队列、测试或部署路径的项目。
- 前端/移动端：优先找有真实页面流、状态管理、接口联调、组件体系和可演示交互的项目。
- 全栈：优先找能打通前端、后端、数据库和部署的项目。
- 测试开发：优先找可补测试体系、mock、E2E、CI、覆盖率和压测的项目。
- 数据工程：优先找 ETL、调度、数据质量、指标、warehouse/lakehouse 或流处理项目。
- 云原生/DevOps：优先找 Docker、Kubernetes、CI/CD、observability、gateway、service mesh 或成本优化项目。
- 安全：优先找认证授权、漏洞扫描、输入校验、审计日志、依赖治理或攻防靶场项目。
- 系统/基础架构：优先找网络、存储、编译器、数据库、分布式系统或性能优化项目。
- AI/算法：优先找有数据、模型、评估、demo 或 serving 路线的项目。

## 推荐输出

输出表格包含：

- repo URL
- license 或项目来源备注
- stars / last commit
- JD 匹配点
- 最小运行路径
- 运行资源预估
- 简历标题草稿
- 魔改 idea
- 用户偏好匹配点和不匹配点（仅在用户有有效 taste 时）
- 风险
- 推荐结论：主项目、备选项目、淘汰项目
