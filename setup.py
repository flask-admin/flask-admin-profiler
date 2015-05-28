# Fix for older setuptools
import re
import os

from setuptools import setup, find_packages


def fpath(name):
    return os.path.join(os.path.dirname(__file__), name)


def read(fname):
    return open(fpath(fname)).read()


def desc():
    return read('README.rst')


setup(
    name='Flask-Admin Profiler',
    version='0.0.1',
    url='https://github.com/flask-admin/flask-admin-profiler/',
    license='BSD',
    author='Serge S. Koval',
    author_email='serge.koval+github@gmail.com',
    description='Convenient Flask-Admin plugin to monitor memory and performance of the Flask application',
    long_description=desc(),
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask-Admin>=1.1.0',
        'objgraph==2.0.0'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ])
