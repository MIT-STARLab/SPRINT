# Grab relevant data for cached xlnks/ecl file
# 
# @author Kit Kennedy

import json
import argparse

OUTPUT_JSON_VER = '0.4'

if __name__ == '__main__':

    ap = argparse.ArgumentParser(description='prop data cache file creator')
    ap.add_argument('prop_data_file',
                    type=str,
                    default='nonexistant.json',
                    help='specify orbit prop data file')

    args = ap.parse_args()

    with open(args.prop_data_file,'r') as f:
        prop_data_file = json.load(f)

    
    if not prop_data_file['version'] == "0.3":
        print("prop_data_file['version']")
        print(prop_data_file['version'])
        raise NotImplementedError


    new_json = {}
    new_json['version'] = OUTPUT_JSON_VER
    new_json['scenario_params'] = prop_data_file['scenario_params']
    new_json['accesses_data'] = {}
    new_json['accesses_data']['xlnk_times'] = prop_data_file['accesses_data']['xlnk_times']
    new_json['accesses_data']['xlnk_range'] = prop_data_file['accesses_data']['xlnk_range']
    new_json['accesses_data']['ecl_times'] = prop_data_file['accesses_data']['ecl_times']
    
    print('copied xlnk_times for %d sats'%(len(prop_data_file['accesses_data']['xlnk_times'])))
    print('copied xlnk_range for %d sats'%(len(prop_data_file['accesses_data']['xlnk_range'])))
    print('copied ecl_times for %d sats'%(len(prop_data_file['accesses_data']['ecl_times'])))

    with open('cache_file.json','w') as f:
        json.dump(new_json ,f)