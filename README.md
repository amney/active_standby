# ACI Active / Standby 
Dynamically enable a standby port channel when the active port channel goes down

The major use case for this is for high availability appliance clusters such as firewalls or load balancers.  

Some appliances cannot work in a active/active fashion so we must bring up the standby link on failure of the active.

## Usage Summary
This tool has a couple of requirements:

- You have two port channels configured in ACI
- The "Active" port channel is up
- The "Standby" port channel is admin down (blacklisted)

The tool subscribes over a Websocket to events on the active port channel

When the tool receives an event that the active port channel has gone down it: 

- Attempts to enable the "Standby" port channel
- Attempts to disable (blacklist) the "Active" port channel
- If specified, run a user callback script (for example to send a notification email)
- Depending on the result of enabling the port channel exits with either a success or failure code

At this point the Administrator needs to perform some remediation to bring up the Active link and then disable the Standby link


## Installation

- Clone this repository
- Install using `python setup.py install`

## Installation on an APIC  

> Cisco does not provide TAC support for running user code on the APIC  
> Resource usage is limited by Linux Cgroups   
> Explicitly use `python2.7` as the APIC uses Python 2.6 by default

- Make sure your APIC has DNS and external connectivity to pypi.python.org
- Upload a copy of the tool to your home directory on the APIC
- Add your user local packages directory to your `$PYTHONPATH` 
- `export PYTHONPATH=$PYTHONPATH:/home/admin/.local/lib/python2.7/site-packages/`
- Run `python2.7 setup.py install --user`
- This will install the required dependencies
- Check you can launch the tool with `python2.7 active_standby.py`

## Launching
> The name of a port channel is a unique identifier (called a DN in ACI)
> 
> Because of the way port channels are allocated on switches we must be careful to find the exact name
> 
> To find the name in the APIC UI:
> 
> Navigate to `Fabric > Inventory > Pod 1 > "Desired Leaf" > Interfaces > PC Interfaces > "Desired PC"`
> 
> In the top right hand corner of the UI click the "welcome, {user}" text
> 
> Click "Show Debug Info"
> 
> In the bottom status bar find the text that looks similar to `topology/pod-1/node-101/sys/aggr-[po1]`
> 
> Copy this: it is your Port Channel name!

To launch the tool use  

`python active_standby.py`

To pass your parameters you can either:

- (a) Pass each input parameter before launching using the -- parameters below 

- (b) Export one or more parameters as environment variables 
	(prefix each env variable with AS, e.g. `export AS_APIC_USER="admin"`)  
  
- (c) Answer the interactive prompts at run time
 
```
Usage: active_standby.py [OPTIONS]

Options:
  --apic-address TEXT  DNS or IP address of your APIC
  --apic-user TEXT     User with enough priviledeges to modify fabric
                       interfaces
  --apic-pass TEXT     APIC user password
  --debug              Show detailed websocket information
  --pc-active TEXT     Name of Active Port Channel e.g.
                       topology/pod-1/node-101/sys/aggr-[po1]
  --pc-standby TEXT    Name of Standby Port Channel e.g.
                       topology/pod-1/node-101/sys/aggr-[po2]
  --callback TEXT      Path to executable file that will be run after
                       switchover
  --help               Show this message and exit.
```

## Advanced

### Callback Script
When a failure is detected it is expected some sort of further action or notification should be performed

This can be achieved by specify the path to a callback script using the `--callback` parameter

The callback script can be any executable file. We have included `example_callback.py` for reference.

### High Availability
Because this tool is idempotent you can launch multiple instances pointed at the same pair of port channels for high availability

When a failure is detected all instances subscribed will be notified and attempt to perform the failover.

The APIC will understand this and will handle it gracefully. Both instances will exit on failover

> Please note if you have set up a callback script, all instances will run it on failover

### Monitoring Standby Link
A simple Bash script can be used to continuously monitor both the active and standby links.

On switchover the tool will exit. The secondary link will then by monitored by the tool. To failback to the primary shut the secondary link. This will cause an automatic switchover by the tool at which point it will begin monitoring the primary link