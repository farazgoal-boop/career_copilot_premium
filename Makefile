PYTHON ?= python

.PHONY: setup test run

setup:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

run:
	$(PYTHON) -m desktop_app.main