import pandas
import csv
import json
import os
import sys
from json_gen import to_json
from injected_obs_generator import inject
from gs_gen import create_gs
import dateutil.parser

#Script for creating new SPRINT cases. Every SPRINT case needs the following defined: 
# 1. constellation_config
# 2. operational_profile_config
# 3. sim_case_config
# 4. ground_station_network_config

def create_case(case_name = "NEW_CASE", gen_obs = True, constellation = "example_const", operation= "example_op", sim= "example_sim", ground_station= "example_gs", sat = None):
    inputs = [constellation, operation, sim, ground_station]
    cwd = os.path.abspath(os.getcwd())
    input_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../../', 'inputs/cases'))
    sat_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../../', 'inputs/reference_model_definitions/sat_refs'))
    obs_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../../', 'inputs/reference_model_definitions/obs_refs'))
    
    
    if all(elem[0:7] == "example" for elem in inputs):
        print("Welcome to the case gen. Please provide the following:")
        if case_name =="NEW_CASE":
            case_name = input("Case Name: ") or "NEW_CASE"
            case_path = input_path + '/' + case_name
        gen_obs = input('Generate observations? (True/False, default True) ')
        if gen_obs.lower() == "true" or "t":
            gen_obs = True
        elif gen_obs.lower() == "false" or "f":
            gen_obs = False
        else:
            gen_obs = True
        if gen_obs:
            num_inject = input('How many injected observations per CubeSat? Recommended 2-3: ')
            try: 
                num_inject = int(num_inject)
            except:
                raise('Error! That was not an integer!')
        constellation = input('Constellation location. Press enter for the example. ') or "example_const"
        op_loc = input('Operation. These are the target observation locations. Enter NEW, REFERENCE, GENERATE, or press enter for the example. ') or "example_op"
        if op_loc.lower() == 'new':
            operation = input('Enter the location for the new operation file. ')
        elif op_loc.lower() == 'reference' or op_loc.lower() == 'ref':
            ref = input('Enter the number of the reference. Options are: \n1. Tropics 20 \n2. Tropics 100 \n3. Chesapeake Bay \n4. Zhou 2017\n5. Mid Earth 20 (from -30 to 30 lat)\n6. Generate New\n')
            gen_flag = False
            if ref == '1':
                ref = 'Tropics_20.json'
            elif ref == '2':
                ref = 'Tropics_100.json'
            elif ref == '3':
                ref = 'Chesapeake_Bay.json'
            elif ref == '4':
                ref = 'Zhou_2017.json'
            elif ref == '5':
                ref = 'mid_earth20.json'
            else:
                raise("Error! You did not enter a valid number.")
            operation = cwd+'/operational_profile_config.json'
            os.system('cp '+ obs_path + '/' + ref +' '+ operation)


        elif op_loc.lower() == 'generate' or op_loc.lower() =='gen':
            num = int(input("Number of targets: "))
            lat_min = int(input(("Minimum latitude: ")))
            lat_max = int(input(("Maximum latitude: ")))
            long_min = int(input("Minimum longitude: "))
            long_max = int(input("Maximum longitude: "))
            file_loc = obs_path+'/blank.json'
            os.system('cp '+ file_loc+ ' operational_profile_config.json')
            from obs_gen import observation_generator
            observation_generator(num,lat_min,lat_max,long_min,long_max,'operational_profile_config.json')
            operation = cwd+'/operational_profile_config.json'


        sim = input('Sim location. Press enter for the example. ') or "example_sim"
        gs_loc = input('Ground Station. Enter NEW, REFERENCE, or press enter for the example. ') or "example_gs"
        if gs_loc.lower() == 'new':
            ground_station = input('Enter the location for the new ground station file. ')
        elif gs_loc.lower() == 'reference' or gs_loc.lower() == 'ref':
            ref = input('Enter the number of the reference. Options are: \n1. KSAT Lite \n2. KSAT \n3. NASA Near Earth Network \n4. Spaceflight Systems \n5. Zhou Original\n ')
            if ref == '1':
                ref = 'KSAT_Lite'
            elif ref == '2':
                ref = 'KSAT'
            elif ref =='3':
                ref = 'NASA_Nen'
            elif ref == '4':
                ref = 'SpaceFlight'
            elif ref == '5':
                ref = 'Zhou_Original'
            else:
                raise("Error! You did not enter a valid number.")

            on = input('Enter the stations you want turned on, seperated by a comma with no spaces. They are cAsE sEnSiTiVe. Type ALL for including all. ')
            if on.lower() == 'all':
                pass
            else:
                on= on.split(',')
            dlnk = input('Enter the name of the downlink. Be sure it matches the downlink in your CubeSat. ')
            other = input('Would you like to modify any other parameters? (Y/N, default no) ')
            if other.lower() == 'y':
                ri = input('Enter the replan interval, in seconds: ') or None
                rrw = input('Enter the replan release wait time, in seconds: ') or None
                rf = input('Release first plans immediately? ') or None
                ground_station = create_gs(ref,on,dlnk,ri,rrw,rf)
            else: 
                ground_station = create_gs(ref, on, dlnk)
                
        sat = input('CubeSat location. Press enter if the CubeSat already exists. ') or None

        inputs = [constellation, operation, sim, ground_station]

    if case_name == "NEW_CASE":
        print("No new case name provided. Will be saved as NEW_CASE")
    case_path = input_path + '/' + case_name

    #Names the files need to be saved as to be read by SPRINT, except the cubesat bc that will be different for each
    file_name = {constellation:'constellation_config.json',
                operation:'operational_profile_config.json',
                sim:'sim_case_config.json',
                ground_station:'ground_station_network_config.json'}
    

    try:
        os.mkdir(case_path)
    except FileExistsError:
        print("Path folder already exists.")
    
    example_path = cwd + '/examples/'
    
    #Start with sat bc it needs to go somewhere else
    if sat is not None:
            #get the name. going to assume if it's a json you've named it the right thing...
        file_extension = os.path.splitext(sat)[1]
        if file_extension == '.xlsx':
            excel_data_df = pandas.read_excel(sat, sheet_name = 'Sheet1')
            sat_name= excel_data_df.iat[3,1] +'.json'
            to_json(sat, sat_name)
        else:
            sat_name = os.path.splitext(sat)

        os.system('cp '+ sat_name +' '+ sat_path)
        os.system('rm '+sat_name)

    for elem in inputs:
        cleanup = False
        name = file_name[elem]
        if elem[0:7] == "example":
            json_file = example_path+name
        else: 
            file_extension = os.path.splitext(elem)[1]
            if file_extension == '.json':
                cleanup = True
                json_file = name
                
            else:
                #if it's a constellation, check which sheet to use
                if name == 'constellation_config.json':
                    excel_data_df = pandas.read_excel(elem, sheet_name = 'Sheet1')
                    if excel_data_df.iat[2,1] == 'Plane':
                        sheet = 'Sheet2'
                    elif excel_data_df.iat[2,1] == 'Individual Assignment':
                        sheet = 'Sheet3'
                    elif excel_data_df.iat[2,1] == 'Walker':
                        sheet = 'Sheet4'
                    else:
                        raise("Constellations must be defined by planes, individually, or as a Walker constellation.")
                else:
                    sheet = 'Sheet2'
                to_json(elem, name, sheet)
                cleanup = True
                json_file = name

        os.system('cp '+ json_file +' '+ case_path)
        #injected obs want to work on the copy, not the originals
        json_loc = case_path+'/'+name

        #if we generate injected observations, we need the number of sats
        if gen_obs and name == 'constellation_config.json':
            with open(json_loc,'r+') as f:
                data = json.load(f)
            num_sats = data['constellation_definition']['constellation_params']['num_satellites']
        elif gen_obs and name == 'sim_case_config.json':
            #get start date/time
            with open(json_loc,'r+') as f:
                data = json.load(f)
            start = dateutil.parser.isoparse(data['scenario_params']['start_utc'])
            end = dateutil.parser.isoparse(data['scenario_params']['end_utc'])
            inject(json_loc,num_sats,num_inject,start,end)

        if cleanup:
            os.system('rm '+name)
    run = input("Case creation successful. Would you like to run the case? (Y/N) ")
    if run.lower() == 'y':
        print("Running "+case_name+"...")
        
    elif run.lower() == 'n':
        print("Goodbye!")
    
    



if __name__ == '__main__':
    create_case(*sys.argv[1:])
