PYTHON ?= python3
INSTALL_PY = $(PYTHON) scripts/install.py

.PHONY: install uninstall test compile clean

install:
	$(INSTALL_PY) install

uninstall:
	$(INSTALL_PY) uninstall

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_installer.py' -v

compile:
	$(PYTHON) -m compileall -q src/codex_glm53_subagent tests/test_installer.py

clean:
	$(PYTHON) -c "import shutil,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
