#!/bin/sh


pushd $(dirname $0) >/dev/null

source ./client1.env

python2 ./email_callback.py $ACT $SBY "Failure detected, auto-healing attempted. http://wiki/userstory/apic-mon#active-standby-client1"

popd
