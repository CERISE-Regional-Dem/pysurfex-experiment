#!/usr/bin/env python3

####exec(open('/usr/local/apps/lmod/8.6.8/init/env_modules_python.py').read()); module('load', 'ecflow')
import ecflow
##from ecflow import Defs, Suite, Task, Edit
import time
import os
import json
import datetime



def check_suite_status(suite_name, client):
    suite = client.get_defs().find_suite(suite_name)
    if suite and suite.get_state() == ecflow.State.complete:
        return True
    return False

def date_from_config(config, runlength=datetime.timedelta(days=30)):
    with open(config, 'r') as f:
        cfg = json.load(f)
    times = cfg["general"]["times"]
    dt_end = datetime.datetime.fromisoformat(times["end"].replace("Z", "+00:00"))
    dt_valid = datetime.datetime.fromisoformat(times["validtime"].replace("Z", "+00:00"))
    if dt_valid >= dt_end:
        next_end = dt_valid + runlength
    else: 
        raise ValueError("valid time is less than end time!")
    return next_end


# Connect to the ECFlow server
host = "ecfg-nor3005-1"
port = 3141
client = ecflow.Client(host, port)
client.sync_local()

# Define the suite name
suite_names = ["CARRA_Land_Pv1_v2", "CARRA_Land_Pv1_1991"]

sfx_home = "/home/nor3005/sfx_home/"
program = "/perm/nor3005/github/CERISE_Regional_DEM/CARRA_Land_Pv1_v2/.venv/bin/PySurfexExp"
now = datetime.datetime.now()
print("####  ", now, "  ####")
# Main loop to listen for suite completion
for suite_name in suite_names:
    print("checking ", suite_name)
    if check_suite_status(suite_name, client):
        cfg = f"{sfx_home}/{suite_name}/{suite_name}.json"
        dt_end = date_from_config(cfg).strftime("%Y-%m-%dT%H:%M:%SZ")
        command = f"{program} prod -dtgend {dt_end} -config {cfg}"
        print(command)
        os.system(command)
    else:
        print(f"{suite_name} seems to be running, better not touch")
print("##############")

