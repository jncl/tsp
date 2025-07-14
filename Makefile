install: dist
	./venv/bin/python -m pip install --upgrade --force-reinstall dist/tsp-*-py3-none-any.whl
	./venv/bin/tsp --reload

dist:
	rm -rf dist
	./venv/bin/python -m build --sdist --wheel
	rm -rf src/tsp.egg-info build
	ls -ldh dist/tsp-*

release: release-pypi

release-pypi: dist
	echo twine upload dist/tsp-*

.PHONY: dist
