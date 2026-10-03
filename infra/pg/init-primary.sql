-- PG 主库初始化:复制账号 + 复制权限(幂等)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'replicator') THEN
        CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'repl_pass';
    END IF;
END
$$;

-- 业务库基础 schema(应用表由 Alembic 迁移管理,这里只放基础设施对象)
CREATE TABLE IF NOT EXISTS platform_meta (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO platform_meta(key, value) VALUES
    ('schema_role', 'primary'),
    ('initialized_at', now())
ON CONFLICT (key) DO NOTHING;

-- 流复制 HBA:允许 replicator 从任意容器网段发起复制连接
-- (docker-entrypoint 首次初始化时执行;pg_hba 追加需在数据目录就绪后)
-- 通过 shell 无法在此阶段改 pg_hba;改由 command 参数注入:
