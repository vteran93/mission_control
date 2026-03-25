.PHONY: bootstrap-local test smoke-local smoke-docker e2e-local start-local

bootstrap-local:
	bash scripts/bootstrap_local_env.sh

test:
	./.venv/bin/python -m pytest tests -q

smoke-local:
	bash scripts/smoke_local.sh

smoke-docker:
	bash scripts/smoke_docker.sh

e2e-local:
	./.venv/bin/python scripts/e2e_validate_mission_control.py --allow-missing-langgraph

start-local:
	bash ./start_mission_control.sh
