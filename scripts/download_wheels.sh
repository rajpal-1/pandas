#!/bin/sh

VERSION=$1
DIST_DIR="$(realpath $(dirname -- $0)/../dist)"

if [ -z $VERSION ]; then
    echo "Usage: $0 <version> (where <version> is for example 1.5.3)"
    exit 1
fi

curl "https://anaconda.org/multibuild-wheels-staging/pandas/files?version=${VERSION}" | \
    grep "href=\"/multibuild-wheels-staging/pandas/${VERSION}" | \
    sed -r 's/.*<a href="([^"]+\.whl)">.*/\1/g' | \
    awk '{print "https://anaconda.org" $0 }' | \
    xargs wget -P $DIST_DIR

printf "\nWheels downloaded to $DIST_DIR\nYou can upload them to PyPI using:\n\n"
printf "\ttwine upload pandas/dist/pandas-${VERSION}*.{whl,tar.gz} --skip-existing"
