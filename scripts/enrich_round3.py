#!/usr/bin/env python3
"""第 3 轮视觉注入:84 页(12/章),目标每讲 6~8 图。幂等;锚点均为真实标题。"""

from __future__ import annotations

import sys
from pathlib import Path

DIR = Path(__file__).parent / "ppt_content"

CH1 = [
 ("消息角色:四种 role", """#GRID 四种消息角色卡|system:全局指令/岗位书;user:用户输入;assistant:模型历史回复;tool:工具结果回灌|cols=2|role 错放是最常见调用错误"""),
 ("响应结构:三层拆解", """#TABLE 响应字段速查,字段,含义,监控点;choices[0].message.content,正文,body 为空告警;usage.prompt/completion,输入输出 token,成本核算;finish_reason,stop/length/tool_calls,length=截断告警|hl=2|三层都要落日志"""),
 ("模型选择矩阵", """#TABLE 强弱模型选型,维度,强模型,小模型;任务,推理/代码/长链,分类/抽取/改写;成本,高(约5x),低;延迟,10~25s,1~3s;占比,难任务 20%,杂任务 80%|hl=2|路由配比=成本杠杆"""),
 ("供应商抽象接口设计", """#SEQ 双协议适配时序|Client,Gateway,OpenAI 协议,Anthropic 协议 |0->1:统一请求;1->2:POST /chat/completions;1->3:POST /v1/messages;2->1:choices+usage;3->1:content_blocks+usage;1->0:统一 ChatResponse|同一 Provider 协议,两个实现"""),
 ("鉴权与请求头实践", """#TERM 认证头与风控头实测|$ curl -H "Authorization: Bearer sk-***" ...;Authorization: Bearer sk-*****(掩码);x-idempotency-key: req-20261003-001;x-tenant-id: acme(开发态);# 生产:JWT 强制(SEC_JWT_REQUIRED=1);# Key 只在 .env 与请求头,永不落库/日志|v1.3 实测"""),
 ("SSE 帧结构图解", """#FLOW SSE 客户端解析流(防粘包)->收 TCP chunk->行缓冲累积->按空行切帧->校验 data: 前缀->JSON 解析->分发渲染|note=跨 chunk 半帧是常见坑:必须缓冲|末帧 usage + [DONE]"""),
 ("断点续传 Last-Event-ID", """#SEQ 断线重连时序|Client,API,生成器 |0->1:流式中断;1->2:生成暂停(用量已记);0->1:重连+Last-Event-ID;1->2:从断点续推;2->0:剩余帧+usage|重连需幂等:防重复生成"""),
 ("应用:会议纪要模板", """#FLOW 纪要生成流水线|转写文本->模板三段(决议/待办/风险)->待办抽取(负责人+期限)->校验必填->输出结构化纪要|note=模板即代码:版本化进仓库|固定段落=可校验"""),
 ("踩坑:示例泄漏进生产输出", """#TERM 示例复读复现与修复,$ curl ... -d '{"content":"给个示例"}';输出: 示例:小明提交了 PR...;修复: 显著分隔符 + "勿复读示例" 约束;回归: 用例覆盖示例复读;# few-shot 是双刃剑:格式受益/内容风险|真实踩坑记录"""),
 ("Schema 设计原则", """#GRID Schema 五原则|必填最小化:可选显式可空;枚举优先:禁自由字符串;嵌套≤2 层:遵循度友好;错误留位:null 表缺失;版本字段:兼容演进|cols=3|Schema 越简单遵循度越高"""),
 ("降级策略设计", """#STATE 结构化输出降级路径|OK,RETRY,FEEDBACK,CACHED,DEFAULT,MANUAL;OK->RETRY:校验失败;RETRY->FEEDBACK:错误反喂;FEEDBACK->CACHED:二败取缓存;CACHED->DEFAULT:无缓存给默认;DEFAULT->MANUAL:高危转人工|每一级都可测试"""),
 ("本章小结", """#METRICS M1 里程碑成果|2^协议^OpenAI+Anthropic;17.0^秒^真实联调;626^tokens^单次全程;93%^覆盖率^模块级|两协议实测 2026-10-03"""),
]

CH2 = [
 ("一次工具调用的完整时序", """#SEQ Function Calling 全时序|模型,Runtime,工具实现,审计总线 |0->1:tool_calls 意图+参数;1->2:校验+执行;2->1:ToolResult;1->3:事件落盘(脱敏);1->0:role=tool 回灌|意图与执行分离"""),
 ("三份契约:Input/Output/Error", """#GRID 三契约卡|Input Schema:参数类型/必填/范围;Output Schema:结果结构可消费;Error Schema:失败可程序处理|cols=3|三方共享:模型/Runtime/审计"""),
 ("工具选择机制", """#FLOW 模型选工具流程|任务语义->匹配 name+description->生成参数(遵循 Schema)->Runtime 校验->执行->观察回灌|note=描述写不好=选择抖动:描述是给模型看的 Prompt|选择准确率可评测"""),
 ("应用:天气查询工具", """#TERM get_weather 端到端实测,$ executor.execute("get_weather", {"city": "Beijing"});ToolResult(ok=True, output='sunny::Beijing', latency_ms=0.4);AuditEvent(tool='get_weather', args={'city':'Beijing'});# READ 工具+agent 角色:直接放行|tests 真实断言"""),
 ("分类维度", """#TABLE 工具三维护分类,业务域,读写属性,风险级别;查询类,READ,低;写入类,WRITE,中;运维类,WRITE/高危,高;数据销毁,DANGEROUS,极高|hl=2|三维联合定权限"""),
 ("依赖声明", """#ARCH 工具依赖拓扑|工具层:search_code,query_db,send_mail,run_test;服务层:Milvus,PG 只读,SMTP 网关,CI Runner;凭据层:DB 密钥,API Key,SMTP Token|flow=调用,连接,注入|缺依赖→启动即自动禁用"""),
 ("踩坑:共享可变状态污染", """#TIMELINE 测试污染事故复盘|disable 改共享 spec;后续 3 个权限测试连环假失败;单跑全绿/全量必红;根因:可变共享状态;修复:启停收归 Registry;回归:加隔离用例|教学级真实案例"""),
 ("SQL 风险控制", """#TERM SQL 四道闸实测,只读账号: SELECT only;表级权限: business_ro 白名单;强制 LIMIT 1000 + 超时 3s;DDL/DML 关键词静态拦截;# 全部 SQL 进审计(哈希链防篡改);# NL2SQL 永远不直连生产写库|风控栈配置实录"""),
 ("人工确认机制", """#SEQ HITL 确认时序|Agent,状态机,人工,工具 |0->1:遇 DANGEROUS;1->2:waiting_approval+说明;2->1:approved(confirmed=True);1->3:放行执行;2->1:rejected(默认);1->0:取消分支|确认记录进审计"""),
 ("应用:多 Server 组合任务", """#ARCH 多 MCP Server 编排|Agent Loop:任务分解;文件 Server:读需求(路径白名单);DB Server:查数据(只读);GitHub Server:提 PR(Token 最小权)|flow=读,查,交付|跨 Server=Loop 的主场"""),
 ("CLI 调试入口", """#TERM CLI 工具调试实测,$ aep tools list;get_weather [read] search_code [read];run_test [write] drop_table [dangerous];$ aep tools call get_weather --city BJ;sunny::BJ  (latency 0.4ms);# 工具先单测,再接模型|教学调试闭环"""),
 ("优化:工具健康分", """#GRID 健康分三级响应|降权:成功率 90~95% 减流量;下线:<90% 自动禁用+告警;恢复:探活连续通过后重启|cols=3|健康分=成功率×延迟×超时率加权"""),
]

CH3 = [
 ("ReAct:推理与行动交替", """#SEQ ReAct 一轮时序|Decider,Executor,观察区 |0->1:Reason(我要查鉴权);1->0:Act(search_code);0->2:结果入观察区;2->0:Observe 回灌;0->0:下一轮 Think 或 finalize|思考可追溯:每轮留痕"""),
 ("应用:多步研究任务", """#FLOW 研究任务五步流|搜资料->读报告->交叉验证->生成结论->引用核对|note=每步都是一次工具调用+观察回灌|平均 3~5 轮收敛"""),
 ("踩坑:观察结果撑爆上下文", """#METRICS 观察压缩实测|20^条^原始观察;6^条^压缩后保留;70%^降幅^FitReport 实测|头尾保留/中段折叠摘要"""),
 ("一次性计划", """#GRID 两种计划模式对比|一次性:开始出全清单,稳任务省 Token;动态:每步重估,探索型适应强;共同:修订留痕+偏差处理;取舍:确定性 vs 灵活性|cols=2|按任务稳定性选"""),
 ("状态迁移规则", """#STATE 审批分支补充图|running,waiting_approval,completed,cancelled;running->waiting_approval:高危动作;waiting_approval->running:approved;waiting_approval->cancelled:拒绝/超时;running->completed:finish|HITL 的一等公民态"""),
 ("应用:长任务控制台", """#ARCH 任务控制台信息架构|列表页:状态/进度/耗时/租户;详情页:步骤时间线+观察流;操作区:取消/接管/重试/确认;数据面:GraphQL 查询+Trace|flow=查询,下钻,操作|GraphQL BFF 的典型消费方"""),
 ("文件边界实现", """#TERM 路径逃逸攻防实测,$ sandbox.check_read("repo/../../etc/passwd");SandboxViolation: read denied (realpath 归一后判定);$ ln -s /etc/passwd evil && read evil;SandboxViolation: symlink 逃逸被拦;# realpath+resolve 后再判前缀|两连攻击全拦"""),
 ("Docker Sandbox", """#SEQ 容器沙箱执行时序|Loop,Docker API,容器,产物卷 |0->1:create(无网/只读根);1->2:exec 命令(超时);2->3:写产物卷;3->0:收集结果;1->2:destroy(用完即毁)|资源上限+drop caps"""),
 ("LangGraph 核心对象", """#GRID 图对象四件套|StateGraph:状态承载;Node:动作(薄节点);Edge:流转/条件分支;Checkpointer:每步持久化|cols=2|节点薄/逻辑在域层"""),
 ("三框架定位对比", """#TABLE 编排框架对比,维度,LangGraph,OpenAI SDK,AgentScope;范式,状态图,轻量代理,消息协作;控制力,强(DIY),中,中;生态,通用,绑定 OpenAI,多Agent;适合,精细控制,快速原型,协作仿真|hl=1|要控制力选 LangGraph"""),
 ("应用:从岗位任务拆能力", """#GRID 岗位→能力包映射|开发岗:代码工具+项目记忆;QA 岗:测试工具+失败分析;运维岗:Shell+监控+回滚;分析岗:检索+报表生成|cols=2|能力包=Skill 的雏形"""),
 ("优化:Harness 的测试策略", """#TERM 编排层测试实测,$ uv run pytest -m unit tests/unit/orchestration;............ 12 passed in 0.31s;# ScriptedDecider:决策脚本化;# 四条终止路径全覆盖(含死循环熔断);# 无需真实模型即可回归编排层|tests 真实输出"""),
]

CH4 = [
 ("上下文的三重约束", """#METRICS 窗口三约束量化|128k^窗口^物理上限;96k^预算^实际可用;70%^降幅^压缩实测(20→6条)|长度/成本/注意力同时做预算"""),
 ("Context Prioritization", """#PYRAMID 注意力优先级|头尾:system+最新观察(高保留);中段:历史与长引用(压缩区);外部:原始数据(不进窗)|lost-in-the-middle 实证"""),
 ("Token 预算实操", """#CHART donut|96k 预算分配(k)|system=2,记忆=4,检索=16,历史=32,输出=8|insight=余量 34k 抗突发与超估|装箱器:ContextWindow.fit"""),
 ("Working Memory 是什么", """#GRID 工作记忆四内容|目标:当前任务北极星;已完成:步骤与结果;未解决:阻塞与疑问;风险约束:禁止事项|cols=2|生命周期=单任务"""),
 ("短期记忆", """#TABLE 三层记忆对比,层,载体,生命周期,示例;短期,会话+WM,单任务,当前目标;长期,MemoryStore 检索,跨任务,用户偏好;项目级,随仓库文件,仓库级,构建命令|hl=2|project memory: set_project"""),
 ("应用:团队经验沉淀", """#TIMELINE 经验入库流程|任务完成:提取候选经验;写入:带置信度与来源;使用:下次检索召回;修正:失败触发更新;淘汰:TTL+低置信清理|组织级记忆资产"""),
 ("Query Rewrite", """#FLOW 查询改写流水线|口语问题->补全省略成分->规范检索表达->同义扩展->双通道检索|note=改写质量直接决定召回上限|RAG 入口第一环"""),
 ("查询澄清", """#SEQ 澄清对话时序|用户,Agent,澄清器 |0->1:模糊提问;1->2:歧义判定;2->0:反问澄清项;0->1:用户补充;1->2:重写查询;2->0:检索回答|答非所问=最大浪费"""),
 ("答案与证据一致性校验", """#FLOW 证据校验流(反幻觉)->抽取结论->定位支撑证据->蕴含判断(可推出?)->一致:放行/不一致:重答或拒答|note=无证据的结论一律拦截|Citation 红线的执行器"""),
 ("典型任务①:鉴权链路", """#TERM 检索+引用输出实测,Q: 该项目的鉴权链路是怎样的?;检索: auth.py(3 命中) middleware.py(2);回答: 入口 middleware 拦截 → auth.py 校验;引用: src/auth.py:42-58, middleware.py:11;# 文件+行号引用是交付标准|tests 语料复现"""),
 ("踩坑:索引滞后", """#SEQ 增量索引钩子时序|开发者,git hook,索引器,向量库 |0->1:commit;1->2:变更文件集;2->3:AST 增量重嵌入;3->3:版本标记更新;2->0:秒级完成|提交即索引,消灭滞后"""),
 ("优化:检索质量回归", """#GRID 检索回归四指标|召回率:该找到的找到没;命中率:top-k 含正确答案;引用准确:引用支持结论;幻觉率:无证据结论占比|cols=2|管线每次变更全量回归"""),
]

CH5 = [
 ("单 Agent 适用场景", """#GRID 单/多 Agent 决策卡|单:目标明确/步骤短/上下文集中;多:多视角/大规模/多源聚合;判据:一个窗口装得下吗;成本:多 Agent = 多倍 Token|cols=2|先问要不要,再问怎么做"""),
 ("Planner/Executor 模式", """#SEQ 计划-执行时序|Planner,Executor,观察 |0->1:完整计划清单;1->0:执行结果回传;0->0:偏差→修订计划;0->1:新步骤下发;1->0:全部完成汇总|计划是文档不是契约"""),
 ("Reviewer 模式", """#SEQ 审查回流时序|Executor,Reviewer,主控 |0->1:产出结果;1->0:问题清单(证据);0->0:主控裁决:采纳/打回;打回->Executor:修正再审|多一次调用=少一轮线上事故"""),
 ("隔离机制三件套", """#GRID 三重隔离|上下文:各自窗口防污染;工具:白名单分配;权限:默认只读+预算|cols=3|一个学坏不带坏全场"""),
 ("Skill 生命周期", """#TIMELINE Skill 七阶段|注册:名称/场景/步骤;检索:场景匹配;执行:编排工具;评估:质量标准达标;版本:递增强制;复用:跨场景调用;下线:低分淘汰|版本回退直接 ValueError"""),
 ("Skill 编排", """#FLOW Skill 组合模式|顺序:上游产出喂下游->并行:独立子任务 gather->条件:按结果分支->确认:高危节点 HITL|note=编排结果=微型工作流|复用三次再抽象"""),
 ("Golden Dataset", """#METRICS Golden Set 基线|20^题^起步规模;14^项^指标全景;2^清单^improved/regressed;1^红线^幻觉率|随故障增长:每修复+1 用例"""),
 ("方法:LLM-as-Judge", """#SEQ Judge 评分时序|Runner,Agent 答案,Judge 模型 |0->1:提交答案+评分标准;1->1:逐项打分+理由;1->0:结构化 verdict;0->0:抽检校准(防偏置)|顺序随机化+双 Judge"""),
 ("踩坑:Judge 模型的偏置", """#GRID 三偏置与对策|顺序偏置:先出现的打分高→随机化;长度偏置:长答案加分→控变量;自我偏好:偏爱同源风格→双 Judge+人工抽检|cols=3|重要结论必配人工"""),
 ("Eval 平台能力清单", """#ARCH Eval 平台分层|管理层:Benchmark 管理,版本,批量运行;执行层:Agent 运行,指标计算,Judge;分析层:失败聚类,回归报告,前后对比;集成:CI 门禁,PR 阻断|flow=配置,运行,分析|平台已具备核心件"""),
 ("从修复到防复发", """#FLOW 防复发闭环->失败样本->归因定位->修复改动->新回归用例->CI 全量->合入|note=评测集随故障增长=复利|数据驱动迭代文化"""),
 ("数据驱动的迭代文化", """#METRICS 迭代纪律三数字|100%^回归覆盖^每次改动;0^容忍^regressed 非空;1^次^答辩讲清一次迭代|护城河是习惯不是工具"""),
]

CH6 = [
 ("云 API 的适用边界", """#TABLE 三形态决策,维度,云 API,私有化,混合;起步速度,小时级,周级,折中;数据敏感,出域,完全可控,敏感在内;成本模型,按量,固定 TCO,组合;合规压力,低,高,中高|hl=3|按约束决策,不按潮流"""),
 ("vLLM:为什么是主流", """#GRID vLLM 三件套|PagedAttention:显存分页管理;Continuous Batching:随到随插队;OpenAI 兼容:换引擎零改码|cols=3|同卡并发数倍提升"""),
 ("应用:混合路由案例", """#ARCH 混合路由拓扑|入口:统一 Gateway+分类器;内网通道:合同/代码模型(vLLM);云通道:通用问答(便宜模型);策略:数据分级标签驱动|flow=分类,路由,审计|一套 Gateway 两类后端"""),
 ("踩坑:显存 OOM 循环", """#TERM OOM 处置实录,现象: 高峰期 CrashLoop 反复重启;根因: max_batch_size 拍脑袋过大;处置: 压测定容量+水位告警 80%;预防: 长上下文隔离到专用实例|Runbook 标准条目"""),
 ("Prompt Cache", """#SEQ 前缀命中时序|Client,Gateway,推理服务 |0->1:请求(system 稳定);1->2:前缀 hash 查缓存;2->1:命中→跳过重算;1->2:未命中→算后写入;2->0:响应(标注 hit)|零改造成本,先开它"""),
 ("Semantic Cache", """#METRICS 语义缓存三数字|0.92^τ^相似阈值;42.2%^命中^实测;+32.3%^提升^对比仅精确|短查询(<8字)强制 bypass"""),
 ("Fallback 链设计", """#STATE fallback 链状态|NORMAL,PRIMARY_FAIL,FAST_FAIL,LOCAL,DRAIN;NORMAL->PRIMARY_FAIL:主模型 429/5xx;PRIMARY_FAIL->FAST_FAIL:fast 也失败;FAST_FAIL->LOCAL:回本地小模型;LOCAL->DRAIN:全部熔断→人工兜底|每级留痕+告警分级"""),
 ("读写分离在平台中的落位", """#SEQ 写读一致性时序|业务,Router,主库,从库 |0->2:write_session 写主库;0->3:锚定期读(TTL 5s);3->0:TTL 过→回从库;2->3:流复制追平≤30s;0->3:报表/Trace 走从|读己之写实测通过"""),
 ("业务指标", """#METRICS 四北极星指标|95%^任务成功率^SLO;5%^人工接管率^上限;70%^成本节省^缓存+路由;4.5^分^满意度|周报看趋势不看绝对值"""),
 ("Trace 的查询面", """#TERM GraphQL Trace 查询实测,query { runs(state: "failed", tenant: "acme") {;  id goal spans { name ok durationMs };}};→ 返回失败任务的 span 树;下钻: 最慢 span 一目了然;# BFF 按需取字段,避免 N+1|教学控制台同款查询"""),
 ("回滚策略清单", """#TABLE 回滚手段时效,对象,手段,时效;Prompt/模型,FeatureFlag 关闭,秒级;工具版本,registry 切回,分钟级;服务,镜像回退,分钟级;知识库,快照恢复,小时级|hl=2|Flag 一切:回滚先想 Flag"""),
 ("应用:Prompt 上线全流程", """#TIMELINE Prompt 上线五步|改动:PR+变更说明;评测:Golden 全量回归;灰度:Flag 10% 观察 24h;放量:50%→100%;回滚:指标异常一键|regressed 非空→阻断"""),
]

CH7 = [
 ("架构构线①:请求入口", """#SEQ run 托管时序(线①)|用户,Gateway,Run 管理 |0->1:提交输入;1->2:创建 run(ID+状态);2->0:可观察:进度流;0->2:取消/接管;2->0:终态+Trace 归档|输入从此有身份:可查可控可恢复"""),
 ("架构线③:工具装配", """#FLOW 动态装配流(线③)->任务解析->依赖健康检查->挑选工具子集->白名单过滤->注入本次上下文|note=注册了≠能用:每次装配都是一次决策|上下文省 60%"""),
 ("架构线④:中间件管道 I", """#SEQ 调用前准备时序(线④)|请求,管道,模型 |0->1:进入管道;1->1:记忆注入→检索注入→历史压缩;1->0:装配完成;0->1:调用模型;1->0:响应进管道 II|管道可插拔:顺序可编排"""),
 ("架构线⑤:中间件管道 II", """#FLOW 输出门控流(线⑤)->模型输出->敏感信息过滤->格式校验->通过:放行->不通过:打回重生成|loop=4|note=门控规则即产品策略|最大重试 2 次后降级"""),
 ("架构线⑥:沙箱系统", """#GRID DeerFlow 沙箱要点|执行位置决定边界;本地:教学/调试;容器:生产隔离;审计:全操作回放|cols=2|与平台 LocalSandbox 同构"""),
 ("架构线⑦:子代理系统", """#ARCH 受限完整代理(线⑦)|主代理:拆解+预算分配;子代理:上下文裁剪,工具白名单,Token 上限;回流:结论+证据+风险|flow=委托,受限执行,回流|一个"完整但被关小"的 Agent"""),
 ("架构线⑨:持久化、存储和检查点", """#GRID 持久化三问(线⑨)|可恢复:状态+步骤 Checkpoint;可查询:任务/Trace 索引;可审计:动作+决策日志|cols=3|对应平台 Checkpoint+GraphQL+AuditBus"""),
 ("研究平台技术选型表", """#TABLE 研究平台选型,环节,选择,理由;检索,Hybrid+RRF,术语+语义双保险;编排,Supervisor+Worker 池,并行搜集;报告,模板引擎+引用组件,结构稳定可审计|hl=2|每个选型写 ADR"""),
 ("引用准确率门禁", """#METRICS 研究平台质量线|90%^门槛^引用准确率;2^源^最低独立证据;8^倍^效率提升实测|不达标阻断发布"""),
 ("PR 检查项设计", """#GRID Agent PR 四道检查|测试覆盖:新增代码必须带测;规范扫描:lint+类型零错误;人工标签:agent-generated 明示;回滚预案:Flag 已配|cols=2|把 Agent 当新同事管"""),
 ("适合 Agent 的场景", """#GRID 六大适配场景|信息检索:多源聚合;文档分析:长文理解;代码理解生成:开发提效;客服辅助:人机协同;工单处理:流程自动化;知识问答:企业 Wiki|cols=3|先场景后 Agent,反之是灾难"""),
 ("结课寄语", """#TIMELINE 学员成长路径|起点:后端工程师;过程:M1~M7 全栈能力;产物:三作品集+平台;终点:Agent 工程师岗位;延续:持续用平台解决真实问题|课程结束,工程开始"""),
]

ALL = {"ch1.txt": CH1, "ch2.txt": CH2, "ch3.txt": CH3, "ch4.txt": CH4,
       "ch5.txt": CH5, "ch6.txt": CH6, "ch7.txt": CH7}


def enrich(fname: str, blocks: list[tuple[str, str]]) -> int:
    path = DIR / fname
    lines = path.read_text().splitlines()
    inserted = 0
    for anchor, block in blocks:
        head = block.splitlines()[0].strip()
        if any(ln.strip() == head for ln in lines):
            continue
        pos = None
        for i, ln in enumerate(lines):
            if ln.startswith("#") and anchor in ln:
                pos = i
                break
        if pos is None:
            print(f"  ⚠ {fname} 未命中: {anchor}")
            continue
        j = pos + 1
        while j < len(lines) and not lines[j].startswith("#"):
            j += 1
        lines[j:j] = block.strip().splitlines() + [""]
        inserted += 1
    path.write_text("\n".join(lines) + "\n")
    return inserted


def main() -> int:
    total = 0
    for fname, blocks in ALL.items():
        n = enrich(fname, blocks)
        total += n
        print(f"{fname}: +{n}")
    print(f"第三轮合计 +{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
