# Update old files that have the wrong sat_id version
# 
# @author Kit Kennedy

import json
import argparse

OUTPUT_JSON_VER = '0.4'

if __name__ == '__main__':

    ap = argparse.ArgumentParser(description='prop data file fixer')
    ap.add_argument('prop_data_file',
                    type=str,
                    default='nonexistant.json',
                    help='specify orbit prop data file')

    args = ap.parse_args()

    with open(args.prop_data_file,'r') as f:
        the_json = json.load(f)

    
    if not the_json['version'] == "0.3":
        print("prop_data_file['version']")
        print(the_json['version'])
        raise NotImplementedError

    for data in the_json['sat_orbit_data']:
        print ("changing sat_id '%s' ..."%data["sat_id"])
        new_val = "sat%s"%(data["sat_id"])
        print ("...to sat_id '%s'"%new_val)
        data["sat_id"] = new_val

    out_file_name = 'new_file.json'
    print("saving as %s"%out_file_name)
    with open(out_file_name,'w') as f:
        json.dump(the_json ,f)