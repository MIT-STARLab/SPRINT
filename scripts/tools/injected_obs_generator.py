#! /usr/bin/env python

##
# Python runner for orbit visualization pipeline
# @author Kit Kennedy
#



import random
from datetime import datetime,timedelta
import json

day_start = datetime(2016,2,14,4,0,0)
sats = ["sat0","sat1","sat2","sat3","sat4","sat5"]




the_json = []

for i in range(40):

    sat = random.choice(sats)

    day_frac = random.random()


    the_json.append({
            "sat_id": sat,
            "start_utc": (day_start + timedelta(minutes=day_frac*24*60)).isoformat()+'Z',
            "end_utc": (day_start + timedelta(minutes=day_frac*24*60 + 1)).isoformat()+'Z',
            "indx": i,
            "type": "hardcoded"
        }
    )



with open('output.json','w') as f:
    json.dump(the_json ,f)