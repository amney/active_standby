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

When the tool receives an event that the port channel has gone down it: 

- Attempts to enable the "Standby" port channel
- Depending on the result of enabling the prot channel exits with either a success or failure code

At this point the Administrator needs to perform some remediation to bring up the Active link and then disable the Standby link


## Installation

- Clone this repository
- Install Python requirements
        
        pip install -r requirements.txt

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
  --apic-user TEXT     User with enough priviledges to read aaaModLR
  --apic-pass TEXT     APIC user password
  --debug TEXT         Show detailed websocket information
  --pc-active TEXT     Name of Active Port Channel e.g.
                       topology/pod-1/node-101/sys/aggr-[po1]
  --pc-standby TEXT    Name of Standby Port Channel e.g.
                       topology/pod-1/node-101/sys/aggr-[po2]
  --help               Show this message and exit.
```