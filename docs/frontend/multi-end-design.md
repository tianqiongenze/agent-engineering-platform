# 前端多端设计方案(互联网大厂标准)

> v1.0 · 2026-10-03 · 依据 2026 业界共识调研([跨端成熟度](https://ozrit.com)、[框架选型共识](https://ymitsolutions.com)、[monorepo 标准](https://softaims.com)、[PWA 定位](https://brandrums.com))

## 0. 现状与结论

平台当前**无前端代码**(审计维度 9 得分 3.0)。本方案给出大厂标准的多端架构、
设计系统、性能预算与落地路线;第一优先交付 Web 控制台 MVP。

## 1. 多端形态与选型(决策矩阵)

| 端 | 形态 | 选型 | 理由 |
|---|---|---|---|
| Web 控制台 | 主端 | **Next.js 15 + React 19 + TypeScript** | GraphQL/SSE 生态最成熟;团队复用面最大([共识](https://bluesharklabs.com)) |
| 移动端 | 二期 | **React Native(Expo)** | 与 Web 共享逻辑与 Tokens,大厂 React 团队首选 |
| 轻量看板 | 补充 | **PWA** | 触达快、可安装、低成本([2026 趋势](https://kanhasoft.com)) |
| CLI | 已有 | Python CLI(tools 模块) | 工具调试入口已交付 |
| 图形密集场景 | 按需 | Flutter 模块(嵌入) | 仅当出现 Trace 可视化大屏等重图形需求([选型共识](https://ymitsolutions.com)) |

**决策原则**(调研综合):按团队技能/离线需求/发布节奏/无障碍约束决策,而非跑分;
跨端方案相对原生可省约 40% 成本([实证](https://geminatesolutions.com))。

## 2. 工程架构:Monorepo

```
frontend/
  apps/web/          Next.js 控制台
  apps/mobile/       React Native(Expo)
  packages/ui/       跨端组件库(原子→业务组件)
  packages/tokens/   Design Tokens(单一事实源)
  packages/api/      GraphQL/SSE client + 生成类型
  tooling: Turborepo + pnpm workspaces(2026 多应用标准)
```

## 3. 设计系统(大厂标准四层)

1. **Tokens**:色彩/间距/字阶/动效时长,深空蓝主题(与 PPT 视觉同源),暗色优先;
2. **原语组件**:Button/Input/Table/Drawer(无业务语义);
3. **业务组件**:AgentRunCard/TraceTimeline/StreamConsole/CostChart/EvalReport;
4. **页面模板**:控制台布局(左任务树+中时间线+右详情)。

## 4. 性能预算(上线门禁,违反即 CI 红)

| 指标 | 预算 | 度量 |
|---|---|---|
| FCP | < 1.5s | Lighthouse CI |
| LCP | < 2.5s | Lighthouse CI |
| TTI | < 3.0s | Lighthouse CI |
| Bundle(JS 首屏) | < 180KB gzip | size-limit |
| SSE 首字渲染 | < 200ms(收到首帧→上屏) | RUM |

## 5. 与平台能力的直连设计

| 平台能力 | 前端消费 |
|---|---|
| GraphQL BFF | 任务列表/Trace 树/Eval 报表/成本看板(按需取字段) |
| SSE /v1/chat/completions | StreamConsole 打字机 + 末帧 usage 显示 |
| FeatureFlags | 前端灰度直连(同 key 同判定,一致性哈希) |
| AuditEvent | 操作留痕展示(脱敏后) |
| Runbook 告警 | 状态条 + 一键处置跳转 |

## 6. 大厂工程规范清单

- **错误边界+降级 UI**(每路由);**Skeleton 骨架屏**;空态/异常态/加载态三态规范
- **埋点**:路由 PV/核心动作点击/接口耗时(RUM 对齐后端 P95)
- **国际化**:i18n 键值入库(中/英),CJK 排版规则(标点悬挂)
- **无障碍**:WCAG 2.1 AA(对比度≥4.5:1/键盘可达/aria)
- **安全**:CSP/仅 https/token 不落 localStorage(内存+刷新令牌)
- **灰度发布**:前端版本与平台 FeatureFlag 联动,按用户桶逐步放量
- **微前端**:仅当多团队并行失控时启用(qiankun/Module Federation),默认不引入

## 7. 落地路线

- **MVP(2 周)**:apps/web = 登录占位 + 任务列表 + Run 详情(Trace 树)+ StreamConsole
- **V1(+2 周)**:Eval 报表 + 成本看板 + PWA 看板 + Lighthouse CI 门禁
- **V2**:React Native 移动端(任务审批推送/指标卡片)
