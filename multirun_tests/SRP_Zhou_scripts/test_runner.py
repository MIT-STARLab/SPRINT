# this file is intended for setting up and running multiple SPRINT runs, where the config is changed
# in between runs
import json
from subprocess import Popen
# things to modify
# r'..\inputs\reference_model_definitions\sat_refs\zhou_original_sat.json': NVM - only doing Xlnk-always

# setup things to step through
# r'..\inputs\cases\orig_circinus\zhou\sim_case_config.json': ['scenario_params']['sim_run_perturbations']['schedule_disruptions']
schedule_disruptions_list = [
    {"G0": [["2016-02-14T04:00:00.000000Z","2016-02-15T04:00:00.000000Z"]]},
    {"G1": [["2016-02-14T04:00:00.000000Z","2016-02-14T16:00:00.000000Z"]]},
    {"G2": [["2016-02-14T04:00:00.000000Z","2016-02-15T04:00:00.000000Z"]]}
]

# r'..\inputs\general_config\lp_general_params_inputs.json':  ['lp_general_params']['use_self_replanner']
SRP_settings_list = [True, False]

SD_file = r'C:\Users\User\circinusGit\SPRINT\inputs\cases\orig_circinus_zhou\sim_case_config.json'
SRP_file = r'C:\Users\User\circinusGit\SPRINT\inputs\\general_config\lp_general_params_inputs.json'
scripts_folder = r"C:\Users\User\circinusGit\SPRINT\scripts"
# NOTE: NEED TO BE IN SCRIPTS DIRECTORY TO FIND windows_env_var_setup.bat
for SD_setting in schedule_disruptions_list:

    with open(SD_file, "r") as jsonFile:
        data = json.load(jsonFile)

    data['scenario_params']['sim_run_perturbations']['schedule_disruptions'] = SD_setting

    print('Setting schedule disruptions to: %s' % SD_setting)
    with open(SD_file, "w") as jsonFile:
        json.dump(data, jsonFile, indent=4, separators=(',', ': '))
    
    for SRP_setting in SRP_settings_list:
        with open(SRP_file, "r") as jsonFile:
            data = json.load(jsonFile)

        data['lp_general_params']['use_self_replanner'] = SRP_setting

        print('Setting SRP to: %s' % SRP_setting)
        with open(SRP_file, "w") as jsonFile:
            json.dump(data, jsonFile, indent=4, separators=(',', ': '))

        print('New Settings Set - run batch file')

        # python runner_const_sim.py --inputs_location /c/Users/wcgru/Documents/GitHubClones/SPRINT/scripts/../inputs --case_name orig_circinus_zhou --restore_pickle "" --remote_debug false

        p = Popen(r"C:\Users\User\circinusGit\SPRINT\scripts\windows_launcher.bat")
        stdout, stderr = p.communicate()