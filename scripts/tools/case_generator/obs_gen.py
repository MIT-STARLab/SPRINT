#for when you just want a bunch of obs in a certain area
import json
import random
import sys


def observation_generator(num_targets, lat_min,lat_max,long_min, long_max, file_location = None):
       
    targets = []
    for i in range(int(num_targets)):
        
        lat = random.randint(int(lat_min),int(lat_max))
        lon = random.randint(int(long_min), int(long_max))

        targ = {
            "id": "obs" + str(i),
            "name": "generated" +str(i),
            "name_pretty": "generated" +str(i),
            "latitude_deg": lat,
            "longitude_deg": lon,
            "height_m": 0
        }

        targets.append(targ)
    
    if file_location is None:
        print("No file given to inject into. Will dump json into this directory as obs_out.json.")
        data = {}
        data['targets'] = targets
        with open('obs_out.json','w') as f:
            json.dump(data,f, indent =4)
    else:
        with open(file_location,'r+') as f:
            data = json.load(f)

        data['ops_profile_params']['obs_params']['num_targets'] = int(num_targets)
        data['ops_profile_params']['obs_params']['targets'] = targets
        data['ops_profile_params']['obs_params']['target_set_name'] = "Generated targets, using latitude in the range " + str(lat_min) +" to "+ str(lat_max) + ' and longitude in the range '+str(long_min) + " to " +str(long_max)+'.'
        with open(file_location,'w') as f:
            json.dump(data,f,indent =4)
    


if __name__ == '__main__':
    observation_generator(*sys.argv[1:])