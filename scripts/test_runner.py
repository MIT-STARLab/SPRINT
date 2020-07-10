# this file is intended for setting up and running multiple SPRINT runs, where the config is changed
# in between runs
import json
from subprocess import Popen
from copy import deepcopy
case_name = r'\walker15_inc30'
##### SET YOUR REPO DIR HERE BASED ON YOUR PATH #####
#SPRINT_repo = r'C:\Users\wcgru\circinusGit\SPRINT'
SPRINT_repo = r'C:\Users\wqg0901\Documents\warrengr\SPRINT'
#####################################################
windows_launcher_file = SPRINT_repo + r"\scripts\windows_launcher.bat" # not implemented yet for mac / linux
# setup things to step through
# r'..\inputs\cases\orig_circinus\zhou\sim_case_config.json': ['scenario_params']['sim_run_perturbations']['schedule_disruptions']


# r'..\inputs\general_config\lp_general_params_inputs.json':  ['lp_general_params']['use_self_replanner']
SRP_settings_list = [False]
case_folder =  SPRINT_repo + r'\inputs\cases' + case_name
SD_file = case_folder + r'\sim_case_config.json'
SRP_file = SPRINT_repo + r'\inputs\\general_config\lp_general_params_inputs.json'
scripts_folder = SPRINT_repo + r'\scripts'

# Case Settings: (to select a subset of a set of already propagated and access calculated data)
# NOTE: need to change original orbit prop data that has the full set to orbit_prop_data_full.json!
full_orbit_prop_file = case_folder + r'\autogen_files\orbit_prop_data_full.json'
with open(full_orbit_prop_file, "r") as jsonFile:
    full_orbit_prop_data = json.load(jsonFile)
accesses_data = full_orbit_prop_data['accesses_data'] # we only need / mutate accesses_data here, no need to look at sat_orbit_data or scenario_params
num_sats = len(accesses_data['dlnk_aer'])
total_gs = len(accesses_data['dlnk_aer'][0])
total_targs = len(accesses_data['obs_aer'][0])

## Zhou case ##
#"start_utc": "2016-02-14T04:00:00.000000Z",
#"end_utc": "2016-02-15T04:00:00.000000Z",
GS_subsets = [list(range(0,total_gs))] # include all ground stations in one subset
targ_subsets = [list(range(0,total_targs))] # include all targets in one subset
###############

## WALKER CASES ##
#"start_utc": "2018-01-18T00:00:00.000000Z",
#"end_utc": "2018-01-18T06:00:00.000000Z",
#GS_subsets = [[3,5,6,14],[13,14,15,3,4,5,6,8,12]]
GS_subsets = [[3,5,6,14]] #G0 only
#GS_subsets = [[13,14,15,3,4,5,6,8,12]] # G1 only
# GS: descriptions:
# - subset 0: three US stations (NM, Hawaii, Florida) and one pacific station (Guam) (69 unique downlink windows)
# - subset 1: all stations within 30 deg latitude of equator (132 unique downlink winds)
n_targs = 15
#targ_subsets = [list(range(40,60)),list(range(0,total_targs,int(total_targs/n_targs)))] # first is all equatorial set, 2nd is spread out at all latitudes
targ_subsets = [list(range(40,60))] #t0 only
#targ_subsets = [list(range(0,total_targs,int(total_targs/n_targs)))] #t1 only
# target descriptions:
# - susbet 0: all equatorial obs at all longitudes (20 obs -> 65 unique obs windows)
# - subset 1: spread out between -24 and 24 deg lat, various longitudes (15 obs -> 69 unique obs windows)
###################

settings_by_setting_name = {}

dlnk_keys = ['dlnk_aer','dlnk_times']
targ_keys = ['obs_aer','obs_times']
# list of scenarios to skip (already computed)
skip_list = []
for g_setting_ind,GS_subset in enumerate(GS_subsets):
    for t_setting_ind, t_subset in enumerate(targ_subsets):
        # save setting name string to write to mutated orbit prop data
        setting_name = 'setGS_%d_setT_%d_%s' % (g_setting_ind,t_setting_ind,case_name[1:])

        # make a deep copy of the full orbit prop data
        temp_orbit_prop_data = deepcopy(full_orbit_prop_data)
        accesses_data = temp_orbit_prop_data['accesses_data'] # we only need / mutate accesses_data here, no need to look at sat_orbit_data or scenario_params

        # loop through each sat to mutate accesses data (each list is indexed by sat first)
        # NOTE: we set "non-utilized" gs or targs to empty lists, so they technically have no "accesses", but they are still in the sim
        # this was done because I believe the sim takes in the IDs and indexes from the original files, so it would have to be changed
        # further downstream if the indices are changed by "removing" the gs / targs that aren't in each subset
        for sat_ind in range(num_sats):
            # loop through ground station relevant keys
            for key in dlnk_keys:
                new_list = [accesses_data[key][sat_ind][gs_ind] if gs_ind in GS_subset else [] for gs_ind in range(total_gs)]
                accesses_data[key][sat_ind] = new_list # overwrite old list
            
            for key in targ_keys:
                new_list = [accesses_data[key][sat_ind][t_ind] if t_ind in t_subset else [] for t_ind in range(total_targs)]
                accesses_data[key][sat_ind] = new_list # overwrite old list

        # write to new orbit_prop_data json file
        temp_orbit_prop_data['multirun_setting_name'] = setting_name
        orbit_prop_file = case_folder + r'\autogen_files\orbit_prop_data.json'
        with open(orbit_prop_file, "w") as jsonFile:
            json.dump(temp_orbit_prop_data, jsonFile, indent=4, separators=(',', ': '))

        # calc number of unique populated dlnk windows:
        uniq_winds_stack = [x for by_sat_list in accesses_data['dlnk_times'] for x in by_sat_list if x]
        n_real_dlnks = len([x for stack in uniq_winds_stack for x in stack])

        # calc number of unique populated obs windows:
        uniq_winds_stack = [x for by_sat_list in accesses_data['obs_times'] for x in by_sat_list if x]
        n_real_obs = len([x for stack in uniq_winds_stack for x in stack])

        # NOTE: with this approach, need to make sure "RECOMPUTE_ORBIT_LINK" is set to true in the shell script so that the link calculator re-runs
        settings_by_setting_name[setting_name] = {
            'GS_subset': GS_subset,
            't_subset': t_subset
        }
        # NOTE: NEED TO BE IN SCRIPTS DIRECTORY TO FIND windows_env_var_setup.bat
        schedule_disruptions_list = [
            {}, # for nominal case
            {"G%d" % GS_subset[1]: [["2016-02-14T04:00:00.000000Z","2016-02-14T16:00:00.000000Z"]]}
        ]
        #schedule_disruptions_list = [{}] # for just nominal case
        for SD_setting in schedule_disruptions_list:

            with open(SD_file, "r") as jsonFile:
                data = json.load(jsonFile)

            data['scenario_params']['sim_run_perturbations']['schedule_disruptions'] = SD_setting

            
            with open(SD_file, "w") as jsonFile:
                json.dump(data, jsonFile, indent=4, separators=(',', ': '))
            
            # only go through SRP settings if there is a SD, otherwise skip
            if SD_setting:
                for SRP_setting in SRP_settings_list:
                    GS_disrupted = list(SD_setting.keys())[0]
                    scenario_name = '%d_SRP_Test_SRP_%s_GS_%s_%s' % (num_sats,SRP_setting, GS_disrupted,setting_name)
                    if scenario_name in skip_list:
                        print('Skipping because on skip list: %s' % scenario_name)
                        continue
                    else:
                        # print info about scenario
                        print('Running with Setting Name: %s' % setting_name)
                        print('Ground Station: Non-empty winds: %d, with inds: %s' % (n_real_dlnks,GS_subset))
                        print('Obs: Non-empty winds: %d, wind inds: %s' % (n_real_obs,t_subset))
                        print('Schedule disruptions set to: %s' % SD_setting)
                        print('SRP set to: %s' % SRP_setting)

                    with open(SRP_file, "r") as jsonFile:
                        data = json.load(jsonFile)

                    data['lp_general_params']['use_self_replanner'] = SRP_setting

                    
                    with open(SRP_file, "w") as jsonFile:
                        json.dump(data, jsonFile, indent=4, separators=(',', ': '))

                    print('New Settings Set - run batch file')

                    # python runner_const_sim.py --inputs_location /c/Users/wcgru/Documents/GitHubClones/SPRINT/scripts/../inputs --case_name orig_circinus_zhou --restore_pickle "" --remote_debug false

                    p = Popen(windows_launcher_file)
                    stdout, stderr = p.communicate()
                    # TODO: do something with std err in case that run fails we get the message
            else:
                scenario_name = '%d_Nominal_%s' % (num_sats,setting_name)
                if scenario_name in skip_list:
                    print('Skipping because on skip list: %s' % scenario_name)
                    continue
                else:
                    # print info about scenario
                    print('Running with Setting Name: %s' % setting_name)
                    print('Ground Station: Non-empty winds: %d, with inds: %s' % (n_real_dlnks,GS_subset))
                    print('Obs: Non-empty winds: %d, wind inds: %s' % (n_real_obs,t_subset))
                    print('No schedule disruptions, Nominal Case')
                
                with open(SRP_file, "r") as jsonFile:
                        data = json.load(jsonFile)

                data['lp_general_params']['use_self_replanner'] = False

                
                with open(SRP_file, "w") as jsonFile:
                    json.dump(data, jsonFile, indent=4, separators=(',', ': '))

                print('New Settings Set - run batch file')

                ## this is for windows users, not implemented yet for other users#
                p = Popen(windows_launcher_file)
                stdout, stderr = p.communicate()
                # TODO: do something with std err in case that run fails we get the message




# write settings dict for look up later
settings_file = SPRINT_repo + r'\multirun_tests\last_multirun_settings.json'
with open(settings_file, "w") as jsonFile:
    json.dump(settings_by_setting_name, jsonFile, indent=4, separators=(',', ': '))