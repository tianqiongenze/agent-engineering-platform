"""等待基础设施就绪(Compose 健康检查聚合)。"""

#!/usr/bin/env bash
set -e

wait_for() {
  local name="$1" cmd="$2" retries="${3:-60}"
  echo -n "[infra] waiting for $name ..."
  for _ in $(seq 1 "$retries"); do
    if eval "$cmd" >/dev/null 2>&1; then echo " OK"; return 0; fi
    echo -n "."; sleep 2
  done
  echo " FAILED"; return 1
}

wait_for "pg-primary"  "docker exec ap-pg-primary pg_isready -U agent"
wait_for "pg-replica"  "docker exec ap-pg-replica psql -U agent -tAc 'SELECT pg_is_in_recovery()' | grep -q t"
wait_for "redis"       "docker exec ap-redis redis-cli ping"
wait_for "pulsar"      "curl -sf http://localhost:8080/admin/v2/brokers/health"
wait_for "milvus"      "curl -sf http://localhost:9091/healthz"
echo "[infra] all components healthy."
