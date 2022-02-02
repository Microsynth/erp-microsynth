# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in microsynth/__init__.py
from microsynth import __version__ as version

setup(
	name='microsynth',
	version=version,
	description='Microsynth ERP Applications',
	author='Microsynth, libracore and contributors',
	author_email='info@microsynth.ch',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
