#!/bin/sh

# When running on APIC this may be needed
export PYTHONPATH=$PYTHONPATH:/home/admin/.local/lib/python2.7/site-packages/

# get ACT/SBY from client1.env
source ./client1.env

# base64 decode APIC password
APICPASS=$(base64 -d<<<"${APICPASS64}")

# Only allow single instance
PIDFILE=/var/run/apic-mon.key-client1.pid

# Check if another instance is already running
if [ -r "${PIDFILE}" ];then
	MYPID=$(cat ${PIDFILE})
	if (pgrep -U $MYPID apic-mon.key >/dev/null 2>&1);then
		exit "$0 already running, only 1 instance allowed"
	fi
fi

[ -r "${PIDFILE}" ] || [ ! -f "${PIDFILE}" ] && echo $$ > ${PIDFILE} 
[ ! -r "${PIDFILE}" ] && echo "Cant create pid file: ${PIDFILE}" && exit

function cleanup() {
	[ -r "${PIDFILE}" ] && rm -f "${PIDFILE}"
}

trap cleanup EXIT


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
