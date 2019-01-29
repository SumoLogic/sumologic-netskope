from setuptools import setup, find_packages
from os.path import join, dirname, abspath

here = abspath(dirname(__file__))

with open(join(here, 'VERSION')) as VERSION_FILE:
    __versionstr__ = VERSION_FILE.read().strip()


with open(join(here, 'requirements.txt')) as REQUIREMENTS:
    INSTALL_REQUIRES = REQUIREMENTS.read().split('\n')


with open(join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


CONSOLE_SCRIPTS = [
    'sumologic-netskope-collector=sumologic-netskope-collector.netskope:main'
]

setup(
    name="sumologic-netskope-collector",
    version=__versionstr__,
    packages=find_packages('./'),
    install_requires=INSTALL_REQUIRES,
    # PyPI metadata
    author="SumoLogic",
    author_email="it@sumologic.com",
    description="Sumo Logic collection solution for netskope",
    license="PSF",
    long_description=long_description,
    keywords="sumologic python rest api log management analytics logreduce netskope agent security siem collector forwarder",
    url="https://github.com/SumoLogic/sumologic-netskope",
    zip_safe=True,
    include_package_data=True,
    package_data={'sumologic-netskope-collector': [
        'netskope.conf']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent'
    ],
    entry_points={
        'console_scripts': CONSOLE_SCRIPTS,
    }

)