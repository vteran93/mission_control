.PHONY: bootstrap-local test smoke-local smoke-docker start-local

bootstrap-local:
	bash scripts/bootstrap_local_env.sh

test:
	./.venv/bin/python -m pytest tests -q

smoke-local:
	bash scripts/smoke_local.sh

smoke-docker:
	bash scripts/smoke_docker.sh

start-local:
	bash ./start_mission_control.sh
