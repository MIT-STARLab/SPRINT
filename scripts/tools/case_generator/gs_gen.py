import json
import os
import sys
import shutil


def create_gs(reference, stations_on, dlnk, replan_interval = None, replan_release_wait = None, release_first = None):
    #First, get the reference from the reference folder
    print("Starting GS Generation...")
    cwd = os.path.abspath(os.getcwd())
    name = 'ground_station_network_config.json'
    
    if reference[-5:] != ".json":
        reference = reference+".json"
    gs_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../../', 'inputs/reference_model_definitions/gs_refs'))
    os.system('cp '+gs_path+'/'+reference+' '+cwd+'/'+name)
    
    try:
        with open(name,'r+') as f:
            data = json.load(f)
        
        stations = data['network_definition']['gs_net_params']['stations']
        params = data['network_definition']['sim_gs_network_params']['gsn_ps_params']

    except NameError:
        print("There are no stations in file "+reference)
        os.system('rm '+name)

    good_stations = []
    id = 0
    for s in stations:
        if stations_on == 'all':
            s['id'] = 'G' + str(id)
            id += 1
            s['comm_type'] = dlnk
            good_stations.append(s)
        elif s['name'] in stations_on:
            s['id'] = 'G' + str(id)
            id += 1
            s['comm_type'] = dlnk
            good_stations.append(s)
    
    if replan_interval is not None:
        params['replan_interval_s'] = int(replan_interval)
    if replan_release_wait is not None:
        params['replan_release_wait_time_s'] = int(replan_release_wait)

    if release_first is not None:
        if release_first.lower() == 'true' or release_first.lower() == 't':
            params['release_first_plans_immediately'] = True
        elif release_first.lower() == 'false' or release_first.lower() == 'f':
            params['release_first_plans_immediately'] = False

    data['network_definition']['gs_net_params']['stations'] = good_stations
    data['network_definition']['gs_net_params']['num_stations'] = len(good_stations)

    with open(name,'w') as f:
        json.dump(data, f, indent =4)
        print("Successfully saved new gs.")
    
    return (cwd +'/'+name)
    


        
if __name__ == '__main__':
    create_gs(*sys.argv[1:])