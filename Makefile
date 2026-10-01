SHELL := /bin/bash
PSIZE := $(shell du -sh . 2>/dev/null | cut -f1)

.PHONY: setup infra infra-down dev test test-integration lint typecheck ci clean seed

## 一键安装:uv 自动管理 Python 3.12 并同步依赖
setup:
	uv python install 3.12
	uv sync

## 启动基础设施:PG 主从 + Redis + Pulsar + Milvus
infra:
	docker compose -f docker-compose.infra.yml up -d
	@bash scripts/wait-for-infra.sh

infra-down:
	docker compose -f docker-compose.infra.yml down

## 开发模式运行 API(GraphQL BFF + REST)
dev:
	uv run uvicorn agent_platform.api.app:create_app --factory --reload --port 8000

## 单元测试(CI 同款,零外部依赖)
test:
	uv run pytest -m "unit" --cov --cov-report=term-missing

## 集成测试(需先 make infra)
test-integration:
	uv run pytest -m "integration" --cov --cov-report=term-missing

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy src

ci: lint typecheck test

## 种子数据(演示用工具与示例任务)
seed:
	uv run python -m scripts.seed

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist
