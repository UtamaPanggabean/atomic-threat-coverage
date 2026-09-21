.PHONY: all setup_repo validate plan test clean

all: validate test

setup_repo:
	git submodule sync --recursive
	git submodule update --init --recursive
	python3 scripts/verify_pins.py

validate:
	python3 scripts/verify_pins.py
	python3 -m soc_kb.cli validate

plan:
	python3 -m soc_kb.cli plan --output confluence-plan.json

test:
	pytest -q

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache confluence-plan.json
