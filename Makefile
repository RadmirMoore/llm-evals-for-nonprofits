.PHONY: help eval good bad test ci live judge install-dev

help:
	@echo "Targets:"
	@echo "  make eval    - show good vs bad pass/fail tables (offline)"
	@echo "  make good    - gate on good responses (fails if <100%)"
	@echo "  make bad     - show that bad responses are caught"
	@echo "  make test    - run the pytest suite"
	@echo "  make ci      - what CI runs: good gate + tests"
	@echo "  make live    - grade a live Anthropic model (needs ANTHROPIC_API_KEY)"
	@echo "  make judge   - grade good responses with the LLM judge (needs API key)"
	@echo "  make install-dev - install dev/test dependencies"

install-dev:
	pip install -r requirements-dev.txt

eval:
	python3 src/run_eval.py --responses both

good:
	python3 src/run_eval.py --responses good --fail-under 1.0

bad:
	python3 src/run_eval.py --responses bad

test:
	python3 -m pytest -q

ci: good test

live:
	python3 src/run_eval.py --responses live

judge:
	python3 src/run_eval.py --responses good --judge
