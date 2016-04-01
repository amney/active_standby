import json
import re
import subprocess
import thread
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
            print "[{}] Refreshing subscription ID {}".format(strftime("%H:%M:%S"), sub_id)
            query = "https://{apic_address}/api/subscriptionRefresh.json.json?id={sub_id}".format(sub_id=sub_id,
                                                                                                  apic_address=apic_address)

            resp = s.get(query, verify=False)
            if not resp.ok:
                exit("Failed to refresh subscription ID {}".format(sub_id))

    def refresh_login():
        while True:
            sleep(240)
            print "[{}] Refreshing login".format(strftime("%H:%M:%S"))
            query = "https://{apic_address}/api/aaaRefresh.json.json".format(apic_address=apic_address)

            resp = s.get(query, verify=False)
            if not resp.ok:
                exit("Failed to refresh login")

    def on_message(ws, message):
        message = json.loads(message)
        message = message["imdata"][0]["ethpmAggrIf"]['attributes']

        try:
            active_port_count = int(message['numActivePorts'])
            if active_port_count == 0:
                print "==================================================="
                print "             LOST ALL ACTIVE PORTS                 "
                print "              FLIPPING TO STANDBY                  "
                print "==================================================="

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
                    exit("Failed to flip to Standby Port Channel - CRITICAL ERROR")
                else:
                    print "Flipped to Standby Port Channel."

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
                    exit("Failed to shut Active Port Channel - CRITICAL ERROR")
                    print "Shut Active Port Channel. "

                if callback:
                    print "Attempting to launch callback script"
                    try:
                        subprocess.check_call([callback], shell=True)
                    except OSError as e:
                        print e.message
                        exit("Could not find callback script")
                    except subprocess.CalledProcessError as e:
                        print e.message
                        exit("Callback script ended with a non-successful return code")
                    print "Callback script finished"

                exit("Please fix issue then restart monitoring tool")
        except KeyError:
            print "Saw an event on Active Port Channel but did it did not change the amount of active ports"
        except ValueError:
            print "Could not parse numActivePorts into an integer"

    def on_error(ws, error):
        print error

    def on_close(ws):
        print "Gracefully closed connection to APIC"

    def on_open(ws):
        # Subscribe to Active PC and check it is up
        query = "https://{apic_address}/api/mo/{pc_active}.json?query-target=children&target-subtree-class=ethpmAggrIf&subscription=yes".format(
            pc_active=pc_active,
            apic_address=apic_address)

        resp = s.get(query, verify=False)
        if not resp.ok:
            exit("Failed to subscribe to Active link")

        port_channel = resp.json()['imdata'][0]['ethpmAggrIf']['attributes']

        if port_channel['operSt'] != "up":
            exit("Active Port Channel is not up. Please bring it up before launching tool")

        sub_id = resp.json()['subscriptionId']
        thread.start_new_thread(refresh_subscription, (sub_id,))

        # Query for Active PC and get it's path/name
        query = "https://{apic_address}/api/mo/{pc_active}.json?query-target=self&rsp-subtree=children&rsp-subtree-class=ethpmAggrIf".format(
            pc_active=pc_active,
            apic_address=apic_address)
        resp = s.get(query, verify=False)
        if not resp.ok:
            exit("Failed to query Active link")

        resp = resp.json()['imdata'][0]['pcAggrIf']

        port_channel = resp['children'][0]['ethpmAggrIf']['attributes']
        if port_channel['operStQual'] == 'admin-down':
            exit("Active Port Channel should be admin up")

        pc_name = resp['attributes']['name']
        pc_policy = pc_active.replace('node', 'paths')
        pc_policy = re.sub(r'sys/aggr-\[.*\]', 'pathep-[{}]'.format(pc_name), pc_policy)
        active_standby.port_channel_policy_active = pc_policy

        # Query for Standby PC and check it is down
        query = "https://{apic_address}/api/mo/{pc_standby}.json?query-target=self&rsp-subtree=children&rsp-subtree-class=ethpmAggrIf".format(
            pc_standby=pc_standby,
            apic_address=apic_address)
        resp = s.get(query, verify=False)
        if not resp.ok:
            exit("Failed to subscribe to Standby link")

        resp = resp.json()['imdata'][0]['pcAggrIf']

        port_channel = resp['children'][0]['ethpmAggrIf']['attributes']
        if port_channel['operSt'] == "up":
            exit("Standby Port Channel is up. Please bring it down before launching tool")
        if port_channel['operStQual'] != 'admin-down':
            exit("Standby Port Channel should be admin down")

        pc_name = resp['attributes']['name']
        pc_policy = pc_standby.replace('node', 'paths')
        pc_policy = re.sub(r'sys/aggr-\[.*\]', 'pathep-[{}]'.format(pc_name), pc_policy)
        active_standby.port_channel_policy_standby = pc_policy

        print "Found Port Channel Paths"
        print "    Active: {}".format(active_standby.port_channel_policy_active)
        print "    Stndby: {}".format(active_standby.port_channel_policy_standby)
        print ""
        print "==================================================="
        print ""

    print ""
    print "==================================================="
    print "Active Standby Tool"
    print "==================================================="
    print ""

    print "Authenticating with APIC"
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
        exit(" Failed to authenticate with APIC")

    auth = r.json()["imdata"][0]["aaaLogin"]
    token = auth["attributes"]["token"]
    thread.start_new_thread(refresh_login, ())
    print "  Session token = {token}...".format(token=str.join('', token[0:15]))
    print ""
    print "==================================================="
    print "Subscribing to Port Channel (a) Active"
    print "    {}".format(pc_active)
    print ""
    print "Subscribing to Port Channel (b) Standby"
    print "    {}".format(pc_standby)
    print "==================================================="
    print ""

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
