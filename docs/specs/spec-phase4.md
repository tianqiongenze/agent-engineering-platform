# Spec · 阶段四(M4):Context Engineering、Memory 与 Codebase RAG

> 对应课程第 4 章;实现:`src/agent_platform/context_memory/`

## 1. 目标(In Scope)
上下文预算与压缩、三层记忆(短期/长期/项目级)与任务恢复摘要、混合检索(关键词+语义)与 RRF 融合。

## 2. 接口契约
- `compress_history(messages,keep_head,keep_tail)`:头尾保留,中段折叠为一条 `[summarized N ...]`
- `ContextWindow(budget_tokens).fit(messages) -> (kept, FitReport)`:
  超预算时从最旧非头消息丢弃;FitReport(original/final/compression_ratio)
- `MemoryStore`:
  - 短期:`set_short/get_short`(当前任务/会话)
  - 长期:`add_long(content,source,confidence)` / `search_long(keyword)`(子串检索)
  - 项目级:`project` dict + `set_project`(技术栈/构建命令/约定)
  - `task_summary()`:任务恢复锚点(Context 截断后续跑输入)
- `Chunk(id,text,source)`;`HybridRetriever(corpus).search(query,k)`:
  - 关键词通道:BM25(k1=1.2/b=0.75 简化实现)
  - 语义通道:字符 3-gram 余弦(教学替身;生产换 Embedding+Milvus,接口不变)
  - 融合:RRF(K=60);`ScoredChunk.via` 标注命中通道(bm25/vector/both)

## 3. 验收标准
- [x] AC1 中段摘要压缩且头尾保留:`test_compress_keeps_system_and_recent_within_budget`
- [x] AC2 预算装箱与压缩比报告:`test_context_window_budget_in_tokens`
- [x] AC3 三层记忆读写与检索:`TestMemoryStore` 4 例(含 task_summary 恢复锚点)
- [x] AC4 双通道融合排序:`test_keyword_and_semantic_merged` / `test_rrf_fusion_prefers_hit_by_both_channels`
- [x] AC5 无命中返回空:`test_no_hit_returns_empty`
- [ ] AC6 Milvus 向量通道替换(真 Embedding;integration profile)
- [ ] AC7 代码 AST 分块与 Rerank(Cross-Encoder;第 4 章实验课)
- [ ] AC8 Citation 行号级引用与答案证据一致性校验(依赖 AST 分块)

## 4. Out of Scope
Query Rewrite/Decomposition(Decider 层 Prompt 策略);LLM Wiki 知识治理(平台外工作流,课件讲授);
KV Cache 原理属课件概念页。
