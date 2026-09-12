.PHONY: install dev test serve chat policy lint
install:
	pip install -e .
dev:
	pip install -e ".[dev]"
test:
	pytest -q
serve:
	jarvis serve
chat:
	jarvis chat
policy:
	jarvis policy
lint:
	ruff check jarvis tests
