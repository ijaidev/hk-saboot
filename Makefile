PYTHON ?= python3
export PYTHONPATH := src

.PHONY: test eval fixtures pdf audit-g01 audit-g12 ui e2e mobile install-ui clean

test:
	$(PYTHON) -m unittest discover -s tests -v

eval:
	$(PYTHON) tools/eval_golden.py

fixtures:
	$(PYTHON) tools/make_fixtures.py

pdf:
	$(PYTHON) tools/make_pdf.py data/fixtures/golden/G01_duplicate/statement proof/G01_duplicate/statement.pdf

audit-g01:
	$(PYTHON) -m saboot audit --bundle data/fixtures/golden/G01_duplicate/statement --out proof/G01_duplicate

audit-g12:
	$(PYTHON) -m saboot audit --bundle data/fixtures/golden/G12_multiple/statement --out proof/G12_multiple

ui:
	$(PYTHON) -m saboot.webapp --port 8765

install-ui:
	npm install

e2e:
	bash scripts/run_e2e.sh

mobile:
	bash scripts/run_mobile_check.sh

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
