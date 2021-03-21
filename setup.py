# coding: utf-8

import setuptools
from babel.messages import frontend as babel

setuptools.setup(
    packages=setuptools.find_packages(),
    cmdclass={'compile_catalog': babel.compile_catalog,
              'extract_messages': babel.extract_messages,
              'init_catalog': babel.init_catalog,
              'update_catalog': babel.update_catalog},
)
