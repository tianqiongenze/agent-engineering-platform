# Capstone A · 企业级深度研究平台 MVP

**定位一句话**:让 Agent 自动完成"资料搜集 → 交叉验证 → 结构化分析 → 报告生成",
研究报告从数天缩短到数小时。

对应课程:第 7 章讲 7-2(高阶案例一)。

## 架构蓝图

```
研究问题 ──▶ 主导 Agent(Supervisor)
              ├─ CollectorWorker:HybridRetriever 多源检索(CORPUS 语料替身)
              ├─ VerifierWorker:双源交叉验证,输出核对证据
              └─ 聚合 → report_md():Markdown 报告 + 证据链(来源/引用)
方法论沉淀:SkillRegistry 注册 competitor-analysis 技能(可复用/可评估/可版本化)
```

## 七步实施路径

① 明确研究场景(竞品分析/行业调研/投资尽调)→ ② 封装研究 Skill → ③ 接入数据源 Tool
(搜索引擎/行业库/专利/Wiki/专家图谱)→ ④ 构建研究工作流 → ⑤ 建立证据链(来源/引用/Trace)
→ ⑥ 输出报告(Markdown/HTML/交互文档)→ ⑦ 优化:Skill 复用 + 模板化 + 人工反馈。

## 复用平台组件

`multi_agent.supervisor`(并行+聚合+仲裁)· `context_memory.rag.HybridRetriever`(检索)
· `multi_agent.skill.SkillRegistry`(方法论)。

## 验收标准

- [ ] 任意研究问题返回报告,证据链非空且每条带来源
- [ ] 关键数据点双源核对(verifier 证据 ≥2)
- [ ] Skill 可被场景匹配命中,版本化可升级
- [ ] 产出效率对照:人工流程 vs 平台流程(答辩数据)
