import json
import re
import subprocess
import sys
if sys.version_info[0] == 2:
    import thread
else:
    import _thread
from time import sleep, strftime

import click
import requests
import websocket
from requests.packages import urllib3

urllib3.disable_warnings()


@click.command()
@click.option('--apic-address', help="DNS or IP address of your APIC", prompt=True)
@click.option('--apic-user', help="User with enough priviledeges to modify fabric interfaces", prompt=True)
@click.option('--apic-pass', help="APIC user password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option('--debug', is_flag=True, help="Show detailed websocket information")
@click.option('--pc-active', help="Name of Active Port Channel e.g. topology/pod-1/node-101/sys/aggr-[po1]",
              prompt=True)
@click.option('--pc-standby', help="Name of Standby Port Channel e.g. topology/pod-1/node-101/sys/aggr-[po2]",
              prompt=True)
@click.option('--callback', help="Path to executable file that will be run after switchover")
def active_standby(apic_address, apic_user, apic_pass, pc_active, pc_standby, debug=False, callback=None):
    def refresh_subscription(sub_id):
        while True:
            sleep(50)
            logmsg("Refreshing subscription ID {id}".format(id=sub_id))
            query = "https://{apic_address}/api/subscriptionRefresh.json.json?id={sub_id}".format(sub_id=sub_id,
                                                                                                  apic_address=apic_address)

            resp = s.get(query, verify=False)
            if not resp.ok:
                exit(logmsg("Failed to refresh subscription ID {id}".format(id=sub_id)))

    def refresh_login():
        while True:
            sleep(240)
            logmsg("Refreshing login")
            query = "https://{apic_address}/api/aaaRefresh.json.json".format(apic_address=apic_address)

            resp = s.get(query, verify=False)
            if not resp.ok:
                exit(logmsg("Failed to refresh login"))

    def logmsg(msg):
        print(strftime("[%Y-%m-%d %H:%M] {msg}").format(msg=msg))

    def pc_attr (pc_name):
        try:
            # Query PC and return it's attributes
            query = "https://{apic_address}/api/mo/{pc_name}.json?query-target=self&rsp-subtree=children&rsp-subtree-class=ethpmAggrIf".format(
                pc_name=pc_name,
                apic_address=apic_address)
    
            resp = s.get(query, verify=False)
    
            if not resp.ok:
                return FALSE
    
            pc_agg = resp.json()['imdata'][0]['pcAggrIf']
    
            if pc_agg:
                return pc_agg
        
            return FALSE

        except KeyError:
            logmsg("KeyError in pc_attr")
        except ValueError:
            logmsg("ValError in pc_attr")

  
    def on_message(ws, message):
        jmessage = json.loads(message)
        message = jmessage["imdata"][0]["ethpmAggrIf"]['attributes']

        for sub_id in jmessage['subscriptionId']:

            active_port_count = 0
            if 'numActivePorts' in message:
                active_port_count = int(message['numActivePorts'])
    
            if sub_id == active_standby.standby_sub_id:
                # the event was on the subscription for the standby link, someone unshut it, lets stop that 
    
                # when the standby is unshut, a message is received with operStQual == 'port-channel-members-down'.
                # then after some time if the portchannel comes up the 'numActivePorts' >= 0
                # we'll try catch it on the first message, otherwise wait for following message
    
                being_unshut = False 
                if 'status' in message and 'operStQual' in message:
                    if message['status'] == 'modified' and message['operStQual'] == 'port-channel-members-down':
                        being_unshut = True
    
                if active_port_count > 0 or being_unshut:
                    # shutdown the standby (by blacklisting)
                    query = "https://{apic_address}/api/node/mo/uni/fabric/outofsvc.json".format(apic_address=apic_address)
                    data = {
                        "fabricRsOosPath": {
                            "attributes": {
                                "tDn": "{port_channel_policy}".format(
                                    port_channel_policy=active_standby.port_channel_policy_standby),
                                "lc": "blacklist"
                            }
                        }
                    }
    
                    resp = s.post(query, json=data, verify=False)
                    if not resp.ok:
                        exit(logmsg("Failed to shut Standby Port Channel - CRITICAL ERROR"))
                    logmsg("Active PC was up when Standby PC was brought up so it (standby) was shutdown to avoid disaster.")
        
            if sub_id == active_standby.active_sub_id:
                # the event was on the subscription for the active link
                try:
                    if active_port_count == 0:
                        logmsg("===================================================")
                        logmsg("             LOST ALL ACTIVE PORTS                 ")
                        logmsg("              FLIPPING TO STANDBY                  ")
                        logmsg("===================================================")
        
                        # unshut the standby (by deleting from oos)
                        query = "https://{apic_address}/api/node/mo/uni/fabric/outofsvc.json".format(apic_address=apic_address)
                        data = {
                            "fabricRsOosPath": {
                                "attributes": {
                                    "dn": "uni/fabric/outofsvc/rsoosPath-[{port_channel_policy}]".format(
                                        port_channel_policy=active_standby.port_channel_policy_standby),
                                    "status": "deleted"
                                }
                            }
                        }
        
                        resp = s.post(query, json=data, verify=False)
                        if not resp.ok:
                            exit(logmsg("Failed to flip to Standby Port Channel - CRITICAL ERROR"))
                        else:
                            logmsg("Flipped to Standby Port Channel.")
        
                        # shut the active (by blacklisting)
                        query = "https://{apic_address}/api/node/mo/uni/fabric/outofsvc.json".format(apic_address=apic_address)
                        data = {
                            "fabricRsOosPath": {
                                "attributes": {
                                    "tDn": "{port_channel_policy}".format(
                                        port_channel_policy=active_standby.port_channel_policy_active),
                                    "lc": "blacklist"
                                }
                            }
                        }
        
                        resp = s.post(query, json=data, verify=False)
                        if not resp.ok:
                            exit(logmsg("Failed to shut Active Port Channel - CRITICAL ERROR"))
                        logmsg("Shut Active Port Channel. ")
        
                        if callback:
                            logmsg("Attempting to launch callback script")
                            try:
                                subprocess.check_output([callback], shell=True, stderr=subprocess.STDOUT)
                            except OSError as e:
                                logmsg("OSError: {msg}".format(msg=e.strerror))
                                exit(logmsg("Could not find callback script"))
                            except subprocess.CalledProcessError as e:
                                logmsg("CalledProcessError: {msg}".format(msg=e.output))
                                exit(logmsg("Callback script ended with a non-successful return code"))
                            logmsg("Callback script finished")
        
                        exit(logmsg("Please fix issue then restart monitoring tool"))
                except KeyError:
                    logmsg("Saw an event on Active Port Channel but did it did not change the amount of active ports")
                except ValueError:
                    logmsg("Could not parse numActivePorts into an integer")
        
    def on_error(ws, error):
        logmsg("{msg}".format(msg=error))

    def on_close(ws):
        logmsg("Gracefully closed connection to APIC")

    def on_open(ws):
        # Subscribe to Active PC and check it is up
        query = "https://{apic_address}/api/mo/{pc}.json?query-target=children&target-subtree-class=ethpmAggrIf&subscription=yes".format(
            pc=pc_active,
            apic_address=apic_address)

        resp = s.get(query, verify=False)
        if not resp.ok:
            exit(logmsg("Failed to subscribe to Active link"))

        port_channel = resp.json()['imdata'][0]['ethpmAggrIf']['attributes']

        if port_channel['operSt'] != "up":
            exit(logmsg("Active Port Channel is not up. Please bring it up before launching tool"))

        active_standby.active_sub_id = sub_id = resp.json()['subscriptionId']
        if sys.version_info[0] == 2:
            thread.start_new_thread(refresh_subscription, (sub_id,))
        else:
            _thread.start_new_thread(refresh_subscription, (sub_id,))
        logmsg("Subscribed to Active PC: {pc} Sub ID: {id}".format(pc=pc_active, id=sub_id))

        # Subscribe to Standby PC and ensure it's down
        query = "https://{apic_address}/api/mo/{pc}.json?query-target=children&target-subtree-class=ethpmAggrIf&subscription=yes".format(
            pc=pc_standby,
            apic_address=apic_address)

        resp = s.get(query, verify=False)
        if not resp.ok:
            exit(logmsg("Failed to subscribe to Standby link"))

        port_channel = resp.json()['imdata'][0]['ethpmAggrIf']['attributes']

        if port_channel['operSt'] == "up":
            exit(logmsg("Standby Port Channel is up. Please bring it down before launching tool"))

        active_standby.standby_sub_id = sub_id = resp.json()['subscriptionId']
        if sys.version_info[0] == 2:
            thread.start_new_thread(refresh_subscription, (sub_id,))
        else:
            _thread.start_new_thread(refresh_subscription, (sub_id,))
        logmsg("Subscribed to Stndby PC: {pc} Sub ID: {id}".format(pc=pc_standby, id=sub_id))

        # Query for Active PC and check it is up
        pc_agg = pc_attr(pc_active)
        pc_member = pc_agg['children'][0]['ethpmAggrIf']['attributes']

        if pc_member['operStQual'] == 'admin-down':
            exit(logmsg("Active Port Channel should be admin up"))

        pc_name = pc_agg['attributes']['name']
        pc_policy = pc_active.replace('node', 'paths')
        pc_policy = re.sub(r'sys/aggr-\[.*\]', 'pathep-[{pc}]'.format(pc=pc_name), pc_policy)
        active_standby.port_channel_policy_active = pc_policy

        # Query for Standby PC and check it is down
        pc_agg = pc_attr(pc_standby)
        pc_member = pc_agg['children'][0]['ethpmAggrIf']['attributes']

        if pc_member['operStQual'] != 'admin-down':
            exit(logmsg("Standby Port Channel should be admin down"))

        pc_name = pc_agg['attributes']['name']
        pc_policy = pc_standby.replace('node', 'paths')
        pc_policy = re.sub(r'sys/aggr-\[.*\]', 'pathep-[{pc}]'.format(pc=pc_name), pc_policy)
        active_standby.port_channel_policy_standby = pc_policy

        logmsg("PC Path Active: {pc}".format(pc=active_standby.port_channel_policy_active))
        logmsg("PC Path Stndby: {pc}".format(pc=active_standby.port_channel_policy_standby))

    logmsg("===================================================")
    logmsg("Active Standby Tool")
    logmsg("===================================================")

    logmsg("Authenticating with APIC")
    data = {
        "aaaUser": {
            "attributes": {
                "name": apic_user,
                "pwd": apic_pass
            }
        }
    }

    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    r = s.post('https://{apic_address}/api/aaaLogin.json'.format(apic_address=apic_address), json=data, verify=False)

    if not r.ok:
        exit(logmsg(" Failed to authenticate with APIC"))

    auth = r.json()["imdata"][0]["aaaLogin"]
    token = auth["attributes"]["token"]
    if sys.version_info[0] == 2:
        thread.start_new_thread(refresh_login, ())
    else:
        _thread.start_new_thread(refresh_login, ())
    logmsg("  Session token = {token}...".format(token=str.join('', token[0:15])))

    if debug:
        websocket.enableTrace(True)
    ws = websocket.WebSocketApp("ws://{apic_address}/socket{token}".format(apic_address=apic_address, token=token),
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()


if __name__ == "__main__":
    active_standby(auto_envvar_prefix="AS")
