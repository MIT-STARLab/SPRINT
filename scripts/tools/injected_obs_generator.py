#! /usr/bin/env python

##
# Python runner for orbit visualization pipeline
# @author Kit Kennedy
#



import random
from datetime import datetime,timedelta
import json

# day_start = datetime(2016,2,14,4,0,0)
day_start = datetime(2018,1,18,0,0,0)
# sats = ["sat0","sat1","sat2","sat3","sat4","sat5","sat6","sat7","sat8","sat9"]
sats = ["sat0","sat1","sat2","sat3","sat4","sat5","sat6","sat7","sat8","sat9","sat10","sat11","sat12","sat13","sat14","sat15","sat16","sat17","sat18","sat19","sat20","sat21","sat22","sat23","sat24","sat25","sat26","sat27","sat28","sat29"]

# BIG FAT NOTE: MAKE SURE RANDOMLY GENERATED INJECTED OBS DON'T OVERLAP!!!!


the_json = []
indx = 0
# for i in range(40):
for sat in sats:

    for i in range(10):
        # sat = random.choice(sats)

        day_frac = random.random()


        the_json.append({
                "sat_id": sat,
                "start_utc": (day_start + timedelta(minutes=day_frac*24*60)).isoformat()+'Z',
                "end_utc": (day_start + timedelta(minutes=day_frac*24*60 + 1)).isoformat()+'Z',
                "indx": indx,
                "type": "hardcoded"
            }
        )

        indx+=1



with open('output.json','w') as f:
    json.dump(the_json ,f)