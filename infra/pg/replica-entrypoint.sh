#!/bin/sh
# PG 从库引导:若数据目录为空则从主库 pg_basebackup 建立流复制,然后以 standby 启动。
# 教学拓扑:单机 compose 内演示真实流复制;生产替换为 patroni/repmgr(见 Runbook)。
set -e

PGDATA=/var/lib/postgresql/data
PRIMARY_HOST="${PRIMARY_HOST:-pg-primary}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"
REPLICATION_USER="${REPLICATION_USER:-replicator}"
REPLICATION_PASSWORD="${REPLICATION_PASSWORD:-repl_pass}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "[replica] empty data dir -> pg_basebackup from $PRIMARY_HOST:$PRIMARY_PORT"
    PGPASSWORD="$REPLICATION_PASSWORD" pg_basebackup \
        -h "$PRIMARY_HOST" -p "$PRIMARY_PORT" \
        -U "$REPLICATION_USER" \
        -D "$PGDATA" \
        --pgdata="$PGDATA" \
        -Fp -Xs -P -R \
        --checkpoint=fast
    chmod 700 "$PGDATA"
else
    echo "[replica] existing data dir found -> start as standby"
fi

exec docker-entrypoint.sh postgres
