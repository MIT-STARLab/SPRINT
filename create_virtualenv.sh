#!/bin/bash
# Setup the virtualenv for things to run in. If it already exists, then
# this script will just pip update and reinstall the requirements.
# usage:
#   ./create_virtualenv.sh ubuntu

set -ex

DIR=$(dirname $(realpath $0))
PLATFORM=$1
# default is vanilla ubuntu
[ "$1" == "" ] && PLATFORM="mac"

virtualenv_dir=~/.config/virtualenvs/circinus

# If the virtualenv already exists, just update requirements.
if [ -e "$virtualenv_dir" ]; then
	echo "$virtualenv_dir already exists. We'll just update requirements."
else
	# Setup a new virtualenv based on the platform
    if [ $PLATFORM == "ubuntu" ]; then
        echo "Using ubuntu platform"
        virtualenv -p /usr/bin/python3.5 "$virtualenv_dir"
    fi
    
    if [ $PLATFORM == "mac" ]; then
        echo "Using mac platform"
        virtualenv -p /Library/Frameworks/Python.framework/Versions/3.5/bin/python3 "$virtualenv_dir"
    fi
fi

# Now install requirements.
[ -e "$DIR/requirements.txt" ] && $virtualenv_dir/bin/pip install -r "$DIR/requirements.txt"