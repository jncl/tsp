#!/usr/bin/env python
# vim: set fileencoding=utf-8:

import datetime
import os
import sys

from setuptools import setup


REQUIRES = [
]


setup(name="tsp",
      version="1.0",
      description="Task spooler",
      author="Justin Forest",
      author_email="hex@umonkey.net",
      url="https://umonkey.net/",
      packages=["tsp"],
      package_dir={"tsp": "tsp"},
      #scripts=["extras/task-pull", "extras/task-push"],
      entry_points={"console_scripts": ["tsp=tsp.cli:main"]},
      long_description="Inspired by ts",
      classifiers=["Intended Audience :: Developers"],
      keywords="tasks",
      license="Public Domain",
      install_requires=REQUIRES)
