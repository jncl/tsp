srvc_file := /lib/systemd/system/tsp.service
db_file := ~/.local/share/tsp/tasks.db
log_file := /var/log/tsp/tsp.log

install: dist
	./venv/bin/python -m pip install --upgrade --force-reinstall dist/tsp-*-py3-none-any.whl
	./venv/bin/tsp --replace reload

dist:
	@[ -f $(srvc_file) ] && (sudo systemctl stop tsp.service) || true
	@[ -f $(db_file) ] && $(db_file) || true
	@[ -f $(log_file) ] && rm $(log_file) || true
	@[ -f $(srvc_file) ] && (sudo systemctl start tsp.service) || true
	@[ -f ./tsp.log ] && rm ./tsp.log || true
	rm -rf dist
	./venv/bin/python -m build --sdist --wheel
	rm -rf src/tsp.egg-info build
	ls -ldh dist/tsp-*

release: release-pypi

release-pypi: dist
	echo twine upload dist/tsp-*

.PHONY: dist
