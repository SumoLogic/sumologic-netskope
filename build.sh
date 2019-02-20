#!/usr/bin/env bash

# pip install twine wheel setuptools

rm -r build/ dist/ sumologic_netskope_collector.egg-info/ sumonetskopecollector/__pycache__
rm sumonetskopecollector/*.pyc
python setup.py sdist bdist_wheel
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# pip install --index-url https://test.pypi.org/simple/ sumologic-netskope-collector
