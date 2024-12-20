import io
import os
from setuptools import setup, find_packages

# Read the package metadata from cpnpy/meta.py
meta = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "cpnpy", "meta.py"), "r", encoding="utf-8") as f:
    exec(f.read(), meta)

# Optionally read a long description from README.md
with io.open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name=meta["__title__"],
    version=meta["__version__"],
    description=meta["__description__"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=meta["__author__"],
    author_email=meta["__author_email__"],
    url=meta["__url__"],
    license=meta["__license__"],
    packages=find_packages(exclude=["tests*", "examples*", "extra*"]),
    python_requires=">=3.6",
    install_requires=[
        # Add runtime dependencies here, for example:
        # "some_dependency>=1.0.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
    ],
    include_package_data=True,
    zip_safe=False,
)
