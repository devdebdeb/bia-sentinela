.PHONY: setup test lint eval data eda run clean
export PYTHONPATH := src:.

setup:
	pip install -e ".[dev,llm,data]"

test:
	pytest -q

lint:
	ruff check src tests

data:
	python -m bia_sentinela.data.generator

eda:
	python analysis/eda.py

eval:
	python -m bia_sentinela.eval.run_eval --golden eval_data/golden_set.jsonl --redteam eval_data/redteam_set.jsonl

run:
	streamlit run src/bia_sentinela/app.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
