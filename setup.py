# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name='collatelogs',
    version='0.2.0',
    description='A simple log collator',
    url='http://github.com/tchamberlin/collatelogs',
    author='Thomas Chamberlin',
    author_email='tchamberlin@users.noreply.github.com',
    license='MIT',
    packages=['collatelogs'],
    scripts=['bin/collatelogs'],
    include_package_data=True,
    install_requires=['python-dateutil', 'pyyaml', 'tqdm', 'tzlocal', 'pytz'],
    zip_safe=True,
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        # 'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],




)
