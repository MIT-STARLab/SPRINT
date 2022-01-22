import pandas
import csv
import json
import os
import sys

def dictify(row, working_dict, orbit_list):
    #Recursive function that converts csv file into the proper json formatting
    if len(row) == 2:
        if row[0] not in working_dict:
            working_dict[row[0]] = row[1]
        return 
    elif len(row) > 1 and "LIST" in row[1]:
        #Signifies next items need to be placed in a list. NOTE: This only works for constellations rn. Need to modify. 
        new_dict = dict()
        if len(orbit_list) == 0:
            orbit_list.append(new_dict)
            working_dict[row[0]] = orbit_list
        else:
            orbit_list.append(new_dict)
        return 
    else:
        if row[0] not in working_dict:
            working_dict[row[0]] = dict()
        dictify(row[1:], working_dict[row[0]],orbit_list) 

def gs_parse(l):
    #Parses rows for ground station disruptions.
    working_dict = {}
    for item in l:
        key = item[0]
        vals = [item[1],item[2]]
        if key in working_dict:
            working_dict[key].append(vals)
        else:
            working_dict[key] = list()
            working_dict[key].append(vals)
    return working_dict

def is_int(val):
    try:
        a = float(val)
        b = int(val)
    except ValueError:
        return False
    else:
        return a == b
def is_float(val):
    try:
        float(val)
    except ValueError:
        return False
    else:
        return True

def parse(item,disrupt_flag,orbit_flag):
    item_flag = True
    if is_int(item):
        item = int(item)
    elif is_float(item):
        item = float(item)
    elif '[' in item:
        item = item.replace('&',',')
        item = json.loads(item)
    elif '+' in item:
        item = item.replace('+',',')
    elif item.lower() == 'true':
        item = True
    elif item.lower() == 'false':
        item = False 
    elif 'EMPTY' in item:
        item = dict()
    elif 'Unnamed' in item or len(item) == 0:
        item_flag = False
    elif 'GS_DISRUPT' in item:
        disrupt_flag = True
        item_flag = False
    elif 'ORBIT_ASSIGN' in item:
        orbit_flag = True
        item_flag = False 
    elif 'BLANK' in item:
        item = ""
    return (item, item_flag, disrupt_flag,orbit_flag)

def to_json(file, name = "output.json", sheet = 'Sheet2'):
    file_name, file_extension = os.path.splitext(file)
    full_name = file_name + file_extension
    if file_extension == '.xlsx':
        excel_data_df = pandas.read_excel(file, sheet_name = sheet)
        full_name = file_name+'.csv'
        excel_data_df.to_csv (full_name, index = None)
    elif file_extension == '.csv':
        pass
    else:
        print("Not compatible with file type: ", file_extension)
        return None

    config = {}
    orbit_list = []
    disrupt_flag = False
    orbit_flag = False
    disruptions = []
    with open(full_name, 'r+') as data_file:
        for row in data_file:
            row = row.strip().split(",")
            new_row = []
            #Convert string numbers to floats and remove Unnamed and empty items 
            for item in row:
                parsed_item, item_flag, disrupt_flag, orbit_flag = parse(item,disrupt_flag,orbit_flag)
                if item_flag == True:
                    new_row.append(parsed_item)
            if len(new_row) == 0:
                continue
            #For ground station disruptions. They're handled differently than others.
            elif disrupt_flag:
                disruptions.append(new_row)
                continue
            elif len(orbit_list) == 0:
                dictify(new_row,config,orbit_list)
            else:
                dictify(new_row,orbit_list[len(orbit_list)-1],orbit_list)
    
    if disrupt_flag:
        config['scenario_params']['sim_run_perturbations']['schedule_disruptions'] = gs_parse(disruptions)
    
    if orbit_flag:
        orbit_dict = {}
        excel_data_2 = pandas.read_excel(file, sheet_name = 'Sheet5')
        excel_data_2.to_csv ('temp_orbit_assign.csv', index = None)
        with open('temp_orbit_assign.csv','r+') as data_file:
            for row in data_file:
                row = row.strip().split(",")
                if row[0] == "":
                    continue
                orbits = row[1].split("&")
                orbit_dict[row[0]] = orbits
                    
        config['constellation_definition']['constellation_params']['orbit_params']['sat_ids_by_orbit_name'] = orbit_dict
        os.system('rm temp_orbit_assign.csv')
    
    print("Json successfully made.")
    if name == "output.json":
        print("No name supplied. Saving as output.json.")
    with open(name,'w') as outfile:
        json.dump(config, outfile, indent = 4)

    #Clean up
    if file_extension == '.xlsx':
        os.system('rm '+full_name)
    return 


if __name__ == '__main__':
    to_json(*sys.argv[1:])
