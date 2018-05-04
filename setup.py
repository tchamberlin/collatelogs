from setuptools import setup

setup(
    name='collatelogs',
    version='0.1.1',
    description='A simple log collator',
    url='http://github.com/tchamberlin/collatelogs',
    author='Thomas Chamberlin',
    license='MIT',
    packages=['collatelogs'],
    scripts=['bin/collatelogs'],
    zip_safe=True
)
