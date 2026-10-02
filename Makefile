.PHONY: test lint format

test:
	pytest tests/

lint:
	ruff check .

format:
	ruff format .
