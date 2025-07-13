#!/usr/bin/env python
""" setup.py """
# vim: set fileencoding=utf-8:

from setuptools import setup

REQUIRES = [
]

setup(name="tsp",
      version="2.0",
      description="Task spooler",
      author="Jon Hogg",
      author_email="hogg.jon@gmail.com",
      packages=["tsp"],
      package_dir={"tsp": "tsp"},
      entry_points={"console_scripts": ["tsp=tsp.cli:main"]},
      long_description="Inspired by ts",
      classifiers=["Intended Audience :: Developers"],
      keywords="tasks",
      license="Public Domain",
      install_requires=REQUIRES)
