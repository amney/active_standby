#!/bin/sh

export PYTHONPATH=$PYTHONPATH:/home/admin/.local/lib/python2.7/site-packages/

# get ACT/SBY from client1.env
source ./client1.env

# base64 decode APIC password
APICPASS=$(base64 -d<<<"${APICPASS64}")

# loop forever and swap active/standby in the loop
while (true); do
	python2.7 active_standby.py --apic-address "${APICIP}" --apic-user "${APICUSER}" --apic-pass "${APICPASS}" \
		--pc-standby "${SBY}" \
		--pc-active "${ACT}" \
		--callback ${CALLBACK}

	sleep 15s

	python2.7 active_standby.py --apic-address "${APICIP}" --apic-user "${APICUSER}" --apic-pass "${APICPASS}" \
		--pc-standby "${ACT}" \
		--pc-active "${SBY}" \
		--callback ${CALLBACK}
	
done
