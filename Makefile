.PHONY: help eval good bad test ci live judge lint-pii check install-dev

help:
	@echo "Targets:"
	@echo "  make eval    - show good vs bad pass/fail tables (offline)"
	@echo "  make good    - gate on good responses (fails if <100%)"
	@echo "  make bad     - show that bad responses are caught"
	@echo "  make test    - run the pytest suite"
	@echo "  make ci      - what CI runs: good gate + tests"
	@echo "  make check   - validate eval + config JSON against the schema"
	@echo "  make lint-pii- flag contact-like content in case input/notes"
	@echo "  make live    - grade a live Anthropic model (needs ANTHROPIC_API_KEY)"
	@echo "  make judge   - grade good responses with the LLM judge (needs API key)"
	@echo "  make install-dev - install dev/test dependencies"

install-dev:
	pip install -r requirements-dev.txt

check:
	python3 src/run_eval.py --check

lint-pii:
	python3 scripts/lint_pii.py

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
