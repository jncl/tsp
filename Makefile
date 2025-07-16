install: dist
	./venv/bin/python -m pip install --upgrade --force-reinstall dist/tsp-*-py3-none-any.whl
	./venv/bin/tsp --replace reload

dist:
	@[ -f /lib/systemd/system/tsp.service ] && sscs tsp.service
	@[ -f ~/.local/share/tsp/tasks.db ] && rm ~/.local/share/tsp/tasks.db || true
	@[ -f /var/log/tsp/tsp.log ] && rm /var/log/tsp/tsp.log || true
	@[ -f /lib/systemd/system/tsp.service ] && sscr tsp.service
	@[ -f ./tsp.log ] && rm ./tsp.log || true
	rm -rf dist
	./venv/bin/python -m build --sdist --wheel
	rm -rf src/tsp.egg-info build
	ls -ldh dist/tsp-*

release: release-pypi

release-pypi: dist
	echo twine upload dist/tsp-*

.PHONY: dist
