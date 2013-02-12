#!/usr/bin/env python

import os

from setuptools import setup


def readreq(filename):
    result = []
    with open(filename) as f:
        for req in f:
            req = req.partition('#')[0].strip()
            if not req:
                continue
            result.append(req)
    return result


def readfile(filename):
    with open(filename) as f:
        return f.read()


setup(
    name='aversion',
    version='0.1.0',
    author='Kevin L. Mitchell',
    author_email='kevin.mitchell@rackspace.com',
    description="AVersion WSGI Version Selection Application",
    license='Apache License (2.0)',
    py_modules=['aversion'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Environment :: Web Environment',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Framework :: Paste',
        'Programming Language :: Python',
    ],
    url='https://github.com/klmitch/aversion',
    long_description=readfile('README.rst'),
    entry_points={
        'paste.composite_factory': [
            'aversion = aversion:AVersion',
        ],
    },
    install_requires=readreq('.requires'),
    tests_require=readreq('.test-requires'),
)
