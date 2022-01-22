#! /usr/bin/env python


# @author Kit Kennedy
# @edits Mary Dahl

import random
from datetime import datetime,timedelta
import json
import bisect
import sys
import dateutil.parser

def inject(file_to_inject, num_sats, inject_per_sat,day_start=None,day_end=None):
    if day_start is None or day_end is None:
        with open(file_to_inject,'r+') as f:
            data = json.load(f)
        day_start = dateutil.parser.isoparse(data['scenario_params']['start_utc'])
        day_end = dateutil.parser.isoparse(data['scenario_params']['end_utc'])


    sats= []
    for i in range(int(num_sats)):
        sats.append("S" + str(i))

    the_json = []
    used_fracs = []
    indx = 0

    for sat in sats:
        for i in range(int(inject_per_sat)):
            valid = False
            while not valid:
                overlap = False
                start = random.random()*24*60
                end = start + 1
                #make sure the delta doesn't make it after the end of the day
                if (day_start+ timedelta(minutes=end)) > day_end:
                    continue
                
                #checking to make sure observations don't overlap
                if len(used_fracs) == 0:
                    break
                if start >= (used_fracs[-1] +1 ):
                    break
                else:
                    for frac in used_fracs:
                        if abs(frac - start) <= 1:
                            overlap = True
                            break
                    if overlap:
                        pass
                    else:
                        valid = True

            bisect.insort(used_fracs,start)

            the_json.append({
                    "indx": indx,
                    "end_utc": (day_start + timedelta(minutes=end)).isoformat()[:-6]+'Z',
                    "sat_id": sat,
                    "type": "hardcoded",
                    "start_utc": (day_start + timedelta(minutes=start)).isoformat()[:-6]+'Z',
                }
            )

            indx+=1

    if file_to_inject is None:
        print("No file to inject. Saving as output.json")
        with open('output.json','w') as f:
            json.dump(the_json ,f, indent = 4)
            print("Successfully injected observations.")
    else:
        try:
            with open(file_to_inject,'r+') as f:
                data = json.load(f)

            data['scenario_params']['sim_run_perturbations']['injected_observations'] = the_json
            
            with open(file_to_inject,'w') as f:
                json.dump(data, f, indent =4)
                print("Successfully injected " + str(inject_per_sat) + " observations to " + str(num_sats) +" satellites to "+ str(file_to_inject))

        except NameError:
            print("File to inject does not contain the correct data structures. Generated observations will be saved as output.json")
            with open('output.json','w') as f:
                json.dump(the_json,f,indent=4)
                print("Successfully saved injected observations.")


if __name__ == '__main__':
    inject(*sys.argv[1:])
