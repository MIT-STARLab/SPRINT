# this file is for generating plots / outputs from
# the json files in this folder
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SRP_settings = [True, False]

## WALKER ##
n_targs = 15
total_targs = 100
num_sats = 15
#targ_subsets = [list(range(40,60)),list(range(0,total_targs,int(total_targs/n_targs)))] # first is all equatorial set, 2nd is spread out at all latitudes
targ_subsets = [list(range(40,60))] # for 30 walker
#GS_subsets = [[3,5,6,14],[13,14,15,3,4,5,6,8,12]]
GS_subsets = [[3,5,6,14]] # for 30 walker
############

## Zhou ##
n_targs = 5
num_sats = 6
n_gs = 4
#targ_subsets = [list(range(40,60)),list(range(0,total_targs,int(total_targs/n_targs)))] # first is all equatorial set, 2nd is spread out at all latitudes
targ_subsets = [list(range(n_targs))] 
#GS_subsets = [[3,5,6,14],[13,14,15,3,4,5,6,8,12]]
GS_subsets = [list(range(n_gs))] 
###########

data_folder = r".\multirun_tests"

# grab all data
all_data = {}
# SELECT USE CASE to plot
g_select = 0
t_select = 0
# LOAD DISRUPTED DATA SET
GS_subset = GS_subsets[g_select]
t_subset = targ_subsets[t_select]

setting_name = 'setGS_%d_setT_%d' % (g_select,t_select)
for SRP_setting in SRP_settings:

    GS_disruptions = [
        None,
        "G%d" % GS_subset[1]
        ]
    for GS_disruption in GS_disruptions:
        scenario_name = 'WALKER_%d_SRP_Test_SRP_%s_GS_%s_%s' % (num_sats,SRP_setting, GS_disruption,setting_name) if GS_disruption else 'WALKER_%d_Nominal_%s' % (num_sats,setting_name)

        full_filename = data_folder + "\\" + scenario_name + ".json"
        with open(full_filename, "r") as jsonFile:
            all_data[scenario_name] = json.load(jsonFile)
            # modify names with white spaces and remove distinction between exec and non-exec
            all_data[scenario_name]['Num_Failures_by_Type'] = {**all_data[scenario_name]['Num_Failures_by_Type']['exec'], **all_data[scenario_name]['Num_Failures_by_Type']['non-exec']}
            #del all_data[scenario_name]['Num Failures by Type']
            #all_data[scenario_name]['Percentage_of_Exec_Act_Failure_by_Act'] = all_data[scenario_name]['Percentage of Exec Act Failures by Act']
            #del all_data[scenario_name]['Percentage of Exec Act Failures by Act']


# let's put the data in a more pandas friendly format

for s_ind,scenario_name in enumerate(all_data.keys()):
    dataset = []
    for f_ind,failure_name in enumerate(all_data[scenario_name]['Num_Failures_by_Type'].keys()):
        dataset.append([])
        for act_type_failure_count in all_data[scenario_name]['Num_Failures_by_Type'][failure_name].values():
            dataset[f_ind].append(act_type_failure_count)
    
    df = pd.DataFrame(dataset,index=all_data[scenario_name]['Num_Failures_by_Type'].keys(),columns=all_data[scenario_name]['Num_Failures_by_Type'][failure_name].keys())
    df.to_csv(data_folder + scenario_name + '.txt')
