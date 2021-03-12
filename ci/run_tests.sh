#!/bin/bash -e

# Workaround for pytest-xdist (it collects different tests in the workers if PYTHONHASHSEED is not set)
# https://github.com/pytest-dev/pytest/issues/920
# https://github.com/pytest-dev/pytest/issues/1075
export PYTHONHASHSEED=$(python -c 'import random; print(random.randint(1, 4294967295))')

if [[ "not network" == *"$PATTERN"* ]]; then
    export http_proxy=http://1.2.3.4 https_proxy=http://1.2.3.4;
fi

# Always calculate and upload coverage, as coverage reports are merged by Codecov
# https://docs.codecov.io/docs/merging-reports
COVERAGE="--cov=pandas.io.formats.info --junitxml=junit/test-results.xml --cov-report=xml --cov-report=html"

# If no X server is found, we use xvfb to emulate it
if [[ $(uname) == "Linux" && -z $DISPLAY ]]; then
    export DISPLAY=":0"
    XVFB="xvfb-run "
fi

PYTEST_CMD="${XVFB}pytest -m \"$PATTERN\" -n $PYTEST_WORKERS --dist=loadfile -s --strict-markers --durations=30 $COVERAGE pandas/tests/io/formats/test_info.py"

if [[ $(uname) != "Linux"  && $(uname) != "Darwin" ]]; then
    # GH#37455 windows py38 build appears to be running out of memory
    #  skip collection of window tests
    PYTEST_CMD="$PYTEST_CMD --ignore=pandas/tests/window/ --ignore=pandas/tests/plotting/"
fi

echo $PYTEST_CMD
sh -c "$PYTEST_CMD"
