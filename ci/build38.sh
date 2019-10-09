#!/bin/bash -e
# Special build for python3.8 until numpy puts its own wheels up

sudo apt-get install build-essential xvfb
pip install --no-deps -U pip wheel setuptools
pip install python-dateutil pytz cython pytest pytest-xdist hypothesis

git clone https://github.com/numpy/numpy
cd numpy
python setup.py build_ext --inplace
python setup.py install
cd ..
rm -rf numpy

python setup.py build_ext -inplace
python -m pip install --no-build-isolation -e .

python -c "import sys; print(sys.version_info)"
python -c "import pandas as pd"
python -c "import hypothesis"

# TODO: Is there anything else in setup_env that we really want to do?
# ci/setup_env.sh
