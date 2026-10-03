#!/usr/bin/env python3
"""缓存命中率基准(为审计报告提供实测数字)。

负载模型贴近生产:
  阶段1 冷启动:每键首次访问(miss → 回源 → 回填)
  阶段2 稳态:70% 重复键命中 + 30% 全新键(必然 miss)
运行:uv run python scripts/bench_cache.py
"""

from __future__ import annotations

import random

from agent_platform.shared.cache import TwoLevelCache


def _run(
    name: str, unique_keys: int, steady_lookups: int, fresh_ratio: float, l1_size: int = 256
) -> dict:
    cache = TwoLevelCache(l1_size=l1_size)
    rng = random.Random(42)  # noqa: S311 - 非加密用途

    # 阶段1:冷启动(全部 miss)
    for i in range(unique_keys):
        cache.get_or_load(f"k:{i}", lambda i=i: {"blob": "x" * 128})

    # 阶段2:稳态(重复 + 新键混合)
    fresh = 0
    for _ in range(steady_lookups):
        if rng.random() < fresh_ratio:
            fresh += 1
            cache.get_or_load(f"k:{unique_keys + fresh}", lambda: {"blob": "x" * 128})
        else:
            cache.get_or_load(f"k:{rng.randrange(unique_keys)}", lambda: {"blob": "x" * 128})

    snap = cache.stats.snapshot()
    # 只看稳态段的命中率(扣除冷启动的必然 miss 才有调优意义)——
    # 简化处理:直接报告总体,并单列结构
    print(
        f"{name:22s} lookups={snap['lookups']:6d} l1={snap['l1_hits']:6d} "
        f"l2={snap['l2_hits']:5d} miss={snap['misses']:5d} hit_rate={snap['hit_rate']:.1%}"
    )
    return snap


def main() -> None:
    print("== 多级缓存命中率基准(l1=256, 冷启动+70/30稳态)==")
    results = {}
    results["tool"] = _run("工具结果(30键池)", 30, 6000, 0.3)
    results["rag"] = _run("检索结果(200键池)", 200, 6000, 0.3)
    results["llm"] = _run("LLM 语义(1000键池)", 1000, 6000, 0.3)
    results["mixed"] = _run("混合负载(1000键池)", 1000, 6000, 0.5)

    total_hits = sum(s["l1_hits"] + s["l2_hits"] for s in results.values())
    total = sum(s["lookups"] for s in results.values())
    print(f"\n混合命中率 = {total_hits / total:.1%}")

    bench_semantic()
    print("\n== L1 容量敏感性(工具结果 30 键池,理论 100% 可缓存)==")
    for size in (4, 16, 64, 256):
        _run(f"l1_size={size}", 30, 6000, 0.0, l1_size=size)

    print("\n== 结论要素 ==")
    print("· miss 全部来自冷启动与新键 → 命中率上限 = 稳态重复占比")
    print("· L1 容量过小时高频键被逐出 → L2 兜底但多一跳")
    print("· 调优方向:提高稳态重复占比(归一化缓存键)> 扩 L1 > 扩 L2")


def bench_semantic() -> None:
    """L3 语义缓存对比:同负载下 仅精确 vs 精确+语义(τ=0.92)。"""
    import random as _r

    from agent_platform.shared.semantic_cache import SemanticCache, normalize

    print("\n== L3 语义缓存对比(1000 基准问题,稳态 70% 变体/30% 新键)==")
    rng = _r.Random(7)  # noqa: S311
    bases = [f"请分析模块 {i} 的鉴权链路并给出文件行号引用" for i in range(1000)]

    def paraphrase(b: str) -> str:
        suffix = rng.choice(["", "。", "?", " 怎么看?", "(详细一点)"])
        prefix = rng.choice(["", "请问:", "帮我", "你好,"])
        return prefix + b + suffix

    # A. 仅精确键(小写化归一,无语义)
    exact_hits = 0
    store: dict[str, str] = {}
    for i, b in enumerate(bases):
        store[normalize(b)] = f"a{i}"
    fresh = 0
    for _ in range(6000):
        if rng.random() < 0.3:
            fresh += 1
            store[normalize(f"全新问题{fresh}的鉴权链路分析要求")] = "x"
        else:
            q = paraphrase(rng.choice(bases))
            if normalize(q) in store:
                exact_hits += 1
    exact_rate = exact_hits / 6000

    # B. 精确 + 语义(τ=0.92)
    cache = SemanticCache()
    for i, b in enumerate(bases):
        cache.store(b, f"a{i}")
    sem_hits = 0
    for i in range(1, fresh + 1):
        cache.store(f"全新问题{i}的鉴权链路分析要求", "x")
    for _ in range(6000):
        if rng.random() < 0.3:
            cache.store(f"全新问题{rng.randrange(10**9)}的鉴权链路分析要求", "x")
        else:
            hit, _v, _via = cache.lookup(paraphrase(rng.choice(bases)))
            if hit:
                sem_hits += 1
    snap = cache.stats.snapshot()
    sem_rate = sem_hits / 6000
    print(f"仅精确键命中率   = {exact_rate:.1%}")
    print(f"精确+语义命中率  = {sem_rate:.1%}(semantic_hits={snap['semantic_hits']}, τ=0.92)")
    print(f"提升 = +{(sem_rate - exact_rate):.1%} 绝对值")
    assert sem_rate > exact_rate, "语义层必须带来正收益"


if __name__ == "__main__":
    main()
