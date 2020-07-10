import os.path
import argparse
import json
import sys

import pickle as pkl
from datetime import datetime
from collections import namedtuple
from datetime import timedelta

try: # First try will work if subrepo circinus_tools is populated, or if prior module imported from elsewhere (so this covers all the rest of the imports in this module as well)
    from circinus_tools  import time_tools as tt
    from circinus_tools  import io_tools
    from circinus_tools  import debug_tools
except ImportError:
    print("Importing circinus_tools from parent repo...")
    try:
        sys.path.insert(0, "../")
        from circinus_tools  import time_tools as tt
        from circinus_tools  import io_tools
        from circinus_tools  import debug_tools
    except ImportError:
        print("Neither local nor parent-level circinus_tools found.")
        exit()

try:
    sys.path.insert(0, "../")               # this file can find circinus_sim
    sys.path.insert(0, "../circinus_sim")   # so lp_wrapper.py can find constellation_sim_tools in the course of loading GlobalPlannerWrapper
    sys.path.insert(0, "../circinus_global_planner/python_runner") # so GlobalPlannerWrapper itself can load from runner_gp (it attempts, but from the wrong file depth)
    sys.path.insert(0, "../circinus_global_planner") # runner_gp can find gp_tools in the above
    from circinus_sim.constellation_sim_tools.gp_wrapper import GlobalPlannerWrapper
except ImportError:
    print("Error while importing GlobalPlannerWrapper")
    exit()

try:
    sys.path.insert(0, "../circinus_orbit_link/python_runner")
    from circinus_orbit_link.python_runner import simple_link_calc # py_links_wrapper
except ImportError:
    print("Error while importing Link Calculator")
    exit()

try:
    sys.path.insert(0, "../circinus_orbit_propagation/python_runner")
    from circinus_orbit_propagation.python_runner import runner_orbitprop
except ImportError:
    print("Error while importing Orbit Propagator")
    exit()


from circinus_tools.scheduling.io_processing import SchedIOProcessor
from circinus_tools.activity_bespoke_handling import ActivityTimingHelper
from circinus_sim.constellation_sim_tools.sim_agent_components import PlanningInfoDB

class DotDict(dict):
    """dot.notation access to dictionary attributes"""
    def __getattr__(self, attr):
        return self.get(attr)
    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__

    # Allow for pickling/deep copies:
    def __getstate__(self):
        return self

    def __setstate__(self, state):
        self.update(state)
        self.__dict__ = self

##### Globals #####
global_verbose_flag = False
server = None
gp_wrapper = None
all_windows_dict = None
latest_gp_route_indx = 0
horizon_len_m = 0

tmp_global_of_caseSpecificParams = {}

parameter_updates = None

PATH_TO_INPUTS = None

def __print(note, end='\n', always=False,flush=False):
    if ( global_verbose_flag or always ):
        print(note, end=end, flush=flush)

def main():

    REPO_BASE = os.path.abspath(os.pardir)  # os.pardir aka '..'

    ap = argparse.ArgumentParser()

    # Using default arguments for providing the default location that would be used if not w/in larger CIRCINUS repo.
    # TODO - When we settle on our nominal models, will make this example directory.
    ap.add_argument('--inputs_location',
                    type=str,
                    default=os.path.join(REPO_BASE,'example_input'),
                    help='specify directory in which to find input and config files')

    args = ap.parse_args()
    global PATH_TO_INPUTS
    PATH_TO_INPUTS = args.inputs_location


    # ------- Filenames ------ #

    ### Config files ###
    gp_config_FILENAME = PATH_TO_INPUTS+'/general_config/gp_general_params_inputs.json' # TODO - get this moved into GP

    with open(gp_config_FILENAME,'r') as f:
        gp_general_params = json.load(f)

    global tmp_global_of_caseSpecificParams
    tmp_global_of_caseSpecificParams['gp_general_params'] = gp_general_params

    global horizon_len_m
    horizon_len_m = max( 
                        gp_general_params["gp_wrapper_params"]['gp_params']['planning_horizon_fixed_mins'],
                        gp_general_params["gp_wrapper_params"]['gp_params']['planning_horizon_obs_mins'],
                        gp_general_params["gp_wrapper_params"]['gp_params']['planning_horizon_xlnk_mins'],
                        gp_general_params["gp_wrapper_params"]['gp_params']['planning_horizon_dlnk_mins']
                    ) + gp_general_params["gp_wrapper_params"]['gp_params']['planning_past_horizon_mins']

    sim_params = {
        'gp_general_params' : gp_general_params,

        # Neutering that which we don't want to actually include on init
        # 'output_path'       : None,
        # 'orbit_prop_params' : None,
        # 'orbit_link_params' : None,
        # 'data_rates_params' : None,
        'const_sim_inst_params' : { 
            "gp_wrapper_params"     : gp_general_params["gp_wrapper_params"]
        }
    }


    ################

    global gp_wrapper
    gp_wrapper = GlobalPlannerWrapper(sim_params)


    ##### Relevant Imorts   #####

    from sprint_tools.OEnum import PrintVerbosity
    from IP_Server import IP_Server
    import yaml
    import time

    ##### Load from Configs #####

    with open("cgp_main.yaml", 'r') as stream:
        try:
            yaml_content = yaml.safe_load(stream)
            __print(yaml_content)
        except yaml.YAMLError as exc:
            __print(exc,always=True)

    server_cfg = yaml_content['server_config']

    global server
    server = IP_Server(server_cfg['port'], server_cfg['log_name'], printVerbose=PrintVerbosity.ALL if global_verbose_flag else PrintVerbosity.WARNINGS)   # Lazy - config['omni_port']  # was 54202
    server.setName("Receiver Thread")
    server.start() # listener

    while(1):
        processNextMsg(server)
        __print(".",end='',always=True,flush=True)
        time.sleep(1)

    print("The end!")


def processNextMsg(server, pri=-1):
    next_msg = server.get_msg(pri)
    if ( next_msg is not None ):
        # delivery: 
        if next_msg['req_type'] == 'regenPlan':
            regenerateGP(server, next_msg['payload'])
        elif next_msg['req_type'] == 'updateParams':
            processWholesaleUpdate(next_msg['payload']['scenario_params'])
        elif next_msg['req_type'] == 'addSat':
            addSat(next_msg['payload']['satParams'])
        elif next_msg['req_type'] == 'removeSat':
            removeSat(next_msg['payload']['satID'])
        elif next_msg['req_type'] == 'updateSat':
            updateSatState(next_msg['payload']['satID'], next_msg['payload']['sat_state'])
        elif next_msg['req_type'] == 'quit':
            exit()
        else:
            raise Exception('invalid msg type')


def updateWindows():
    io_proc = SchedIOProcessor(tmp_global_of_caseSpecificParams)

    # parse the inputs into activity windows
    window_uid = 0
    obs_winds, window_uid =io_proc.import_obs_winds(window_uid)
    dlnk_winds, dlnk_winds_flat, window_uid =io_proc.import_dlnk_winds(window_uid)
    xlnk_winds, xlnk_winds_flat, window_uid =io_proc.import_xlnk_winds(window_uid)

    num_sats = tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"]
    if not tmp_global_of_caseSpecificParams["sim_case_config"]["scenario_params"]["use_crosslinks"]: # self.params['sim_case_config']['use_crosslinks']:
        xlnk_winds = [[[]] * num_sats] * num_sats
        xlnk_winds_flat = [[]] * num_sats # list of N_sats empty lists

    ecl_winds, window_uid =io_proc.import_eclipse_winds(window_uid)

    global all_windows_dict
    all_windows_dict = {
        'obs_winds': obs_winds,
        'dlnk_winds': dlnk_winds,
        'dlnk_winds_flat': dlnk_winds_flat,
        'xlnk_winds': xlnk_winds,
        'xlnk_winds_flat': xlnk_winds_flat,
        'ecl_winds': ecl_winds,
        'next_window_uid': window_uid
    }

    global server
    server.latestGP['windows'] = all_windows_dict



def regenerateGP(server, gp_in):
    global gp_wrapper
    server.latestGP["pending"] = True

    if len(tmp_global_of_caseSpecificParams.keys()) <= 1: # one set by default
        print("This should be set as part of remote configuration &/or periodic update before GP used.")
        raise Exception


    curr_time_dt = datetime.now() if gp_in[0] is None else gp_in[0]


    #  get already existing sim route containers that need to be fed to the global planner
    existing_rt_conts = server.plan_db.get_filtered_sim_routes(curr_time_dt,filter_opt='partially_within')

    #  get the satellite states at the beginning of the planning window
    sat_state_by_id = server.plan_db.get_sat_states(curr_time_dt)



    global latest_gp_route_indx
    new_rt_conts, latest_gp_route_indx = gp_wrapper.run_gp(
        curr_time_dt,
        existing_rt_conts,
        tmp_global_of_caseSpecificParams['sim_case_config']['sim_gsn_ID'],
        latest_gp_route_indx,
        sat_state_by_id,
        all_windows_dict,
        tmp_global_of_caseSpecificParams
    )
    
    server.latestGP = {
            "plan" : [ new_rt_conts, latest_gp_route_indx ],
            "windows" : all_windows_dict,
            "timestamp" : tt.date_string(datetime.now()),
            "pending" : False
        }

def loadFromLocalConfig(case_name="ONLINE_OPS"):

    sim_case_config_FILENAME      = PATH_TO_INPUTS+'/cases/'+case_name+'/sim_case_config.json'
    constellation_config_FILENAME = PATH_TO_INPUTS+'/cases/'+case_name+'/constellation_config.json'
    gs_network_config_FILENAME    = PATH_TO_INPUTS+'/cases/'+case_name+'/ground_station_network_config.json'
    opsProfile_config_FILENAME    = PATH_TO_INPUTS+'/cases/'+case_name+'/operational_profile_config.json'
    
    sim_gen_config_FILENAME    = PATH_TO_INPUTS+'/general_config/sim_general_config.json'

    # -------- CASE SPECIFIC CONFIGURATION INPUTS -------- #
    with open(sim_case_config_FILENAME,'r') as f:
        sim_case_config = json.load(f)
    with open(constellation_config_FILENAME,'r') as f:
        constellation_config = json.load(f)
    with open(gs_network_config_FILENAME,'r') as f:
        gs_network_config = json.load(f)
    with open(opsProfile_config_FILENAME,'r') as f:
        opsProfile_config = json.load(f)

    sat_ref_model_FILENAME = PATH_TO_INPUTS+'/reference_model_definitions/sat_refs/'+constellation_config["constellation_definition"]["default_sat_ref_model_name"]+'.json'
    with open(sat_ref_model_FILENAME,'r') as f:
        sat_ref_model = json.load(f)

    payload_ref_model_FILENAME = PATH_TO_INPUTS+'/reference_model_definitions/payload_refs/'+sat_ref_model["sat_model_definition"]["default_payload_ref_model_name"]+'.json'
    with open(payload_ref_model_FILENAME,'r') as f:
        payload_ref_model = json.load(f)

    # -------- General Config ------ #    
    with open(sim_gen_config_FILENAME,'r') as f:     # move to constructor
        sim_gen_config = json.load(f)


    # Peel off outer layer(s)
    scenario_params       = sim_case_config['scenario_params']
    general_sim_params    = sim_gen_config['general_sim_params']
    ops_profile_params    = opsProfile_config['ops_profile_params']
    constellation_params  = constellation_config["constellation_definition"]['constellation_params']
    gs_network_definition = gs_network_config['network_definition']

    sat_model_definition  = sat_ref_model['sat_model_definition']
    payload_params        = payload_ref_model['payload_model_definition']['payload_params']

    ######### ---------- Build orbit_prop_params ---------- #########
    append_power_params_with_enumeration = {
        "power_consumption_W":{
            **sat_model_definition['sat_model_params']['power_params']["power_consumption_W"],
            "obs":payload_params["power_consumption_W"]["obs"]
        },
        "battery_storage_Wh":sat_model_definition['sat_model_params']['power_params']["battery_storage_Wh"],
        'sat_ids':constellation_params['sat_ids'],
        'sat_id_prefix': constellation_params['sat_id_prefix'],
    }
    append_data_params_with_enumeration = {
        **sat_model_definition['sat_model_params']['data_storage_params'],
        'sat_ids':constellation_params['sat_ids'],
        'sat_id_prefix': constellation_params['sat_id_prefix'],
    }
    append_state_params_with_enumeration = {
        **sat_model_definition['sat_model_params']['initial_state'],
        'sat_ids':constellation_params['sat_ids'],
        'sat_id_prefix': constellation_params['sat_id_prefix'],
    }

    power_params_by_sat_id, all_sat_ids1 = io_tools.unpack_sat_entry_list( [ append_power_params_with_enumeration ] , output_format='dict')            
    data_storage_params_by_sat_id, all_sat_ids2 = io_tools.unpack_sat_entry_list( [ append_data_params_with_enumeration ] , output_format='dict')  
    initial_state_by_sat_id, all_sat_ids3 = io_tools.unpack_sat_entry_list( [ append_state_params_with_enumeration ] , output_format='dict') 

    if case_name=="ONLINE_OPS":
        scenario_params['start_utc'] = tt.date_string( datetime.now() )
        scenario_params['end_utc']   = tt.date_string( datetime.now() + timedelta(minutes=horizon_len_m) )
        print("Time range: {} -> {}".format(scenario_params['start_utc'],scenario_params['end_utc']))


    orbit_prop_params = {
        'scenario_params' : {
            'start_utc'     : scenario_params['start_utc'],    # These duplications accomodate runner_gp.py expectations
            'end_utc'       : scenario_params['end_utc'],      # TODO - update runner_gp.py to expect non-duplicated input 
            'start_utc_dt'  : tt.iso_string_to_dt ( scenario_params['start_utc']),
            'end_utc_dt'    : tt.iso_string_to_dt ( scenario_params['end_utc']),
            'timestep_s'    : general_sim_params["timestep_s"]
        },
        'sat_params' : { 
            'num_sats'          : constellation_params['num_satellites'],
            'num_satellites'    : constellation_params['num_satellites'], # Duplication to accomodate downstream (runner_gp.py among others) -- TODO: cut out duplication
            'sat_id_order'      : constellation_params['sat_id_order'],
            'sat_id_prefix'     : constellation_params['sat_id_prefix'],
            'pl_data_rate'      : payload_params['payload_data_rate_Mbps'],
            'payload_data_rate_Mbps'        : payload_params['payload_data_rate_Mbps'], # Duplication to accomodate downstream (runner_gp.py among others) -- TODO: cut out duplication
            'power_params_by_sat_id'        : power_params_by_sat_id,
            'power_params'                  : [ append_power_params_with_enumeration ], # Duplication to accomodate downstream (runner_gp.py among others) -- TODO: cut out duplication
            'data_storage_params_by_sat_id' : data_storage_params_by_sat_id,
            'data_storage_params'       : [ append_data_params_with_enumeration ], # Duplication to accomodate downstream (runner_gp.py among others) -- TODO: cut out duplication 
            'initial_state_by_sat_id'   : initial_state_by_sat_id,
            'initial_state'             : [ append_state_params_with_enumeration ], # Duplication to accomodate downstream (runner_gp.py among others) -- TODO: cut out duplication 
            'activity_params' : {
                **sat_model_definition['sat_model_params']["activity_params"],
                "min_duration_s": {
                    **payload_params["min_duration_s"],
                    **sat_model_definition['sat_model_params']["activity_params"]["min_duration_s"]
                },
                "intra-orbit_neighbor_direction_method":constellation_params["intra-orbit_neighbor_direction_method"]
            }
        },
        'gs_params': { 
            'gs_network_name'   : gs_network_definition["gs_net_params"]['gs_network_name'],
            'num_stations'      : gs_network_definition["gs_net_params"]["num_stations"],
            'num_gs'            : gs_network_definition["gs_net_params"]["num_stations"], # TODO: LOL are you serious right now. Get rid of this duplication.
            'stations'          : gs_network_definition["gs_net_params"]["stations"]
        },
        'obs_params': ops_profile_params['obs_params'],
        'orbit_params': {
                'sat_ids_by_orbit_name' : io_tools.expand_orbits_list(constellation_params['orbit_params'],constellation_params['sat_id_prefix']),
                'sat_orbital_elems'     : constellation_params['orbit_params']['sat_orbital_elems']
            },
        'orbit_prop_data': None # orbit_prop_data   # now from repropagateSats()
    }
    
    # make the satellite ID order. if the input ID order is default, then will assume that the order is the same as all of the IDs found in the power parameters
    orbit_prop_params['sat_params']['sat_id_order'] = io_tools.make_and_validate_sat_id_order( # Pay close attention to this, because this is a mutated copy
        orbit_prop_params['sat_params']['sat_id_order'],
        orbit_prop_params['sat_params']['sat_id_prefix'], 
        orbit_prop_params['sat_params']['num_sats'],
        all_sat_ids1
    )

    io_tools.validate_ids(validator=orbit_prop_params['sat_params']['sat_id_order'],validatee=all_sat_ids1)
    io_tools.validate_ids(validator=orbit_prop_params['sat_params']['sat_id_order'],validatee=all_sat_ids2)
    io_tools.validate_ids(validator=orbit_prop_params['sat_params']['sat_id_order'],validatee=all_sat_ids3)

    gs_id_order = io_tools.make_and_validate_gs_id_order(orbit_prop_params['gs_params'])
    orbit_prop_params['gs_params']['gs_id_order'] = gs_id_order
    orbit_prop_params['gs_params']['elevation_cutoff_deg'] = gs_network_definition["gs_net_params"]["elevation_cutoff_deg"]

    obs_target_id_order = io_tools.make_and_validate_target_id_order(orbit_prop_params['obs_params'])
    orbit_prop_params['obs_params']['obs_target_id_order'] = obs_target_id_order
    ######### ---------- End Build orbit_prop_params ---------- #########



    params = {
        'sim_case_config'   : { 
            'scenario_params' : scenario_params,     # simulation.params['sim_case_config'],
            'sim_gsn_ID' : 'gsn'                     # self.sim_gsn.ID
        },
        'orbit_prop_params' : orbit_prop_params,                        # simulation.params['orbit_prop_params'],
        'orbit_link_params' : {
            "link_disables": ops_profile_params["link_disables"],
            "general_link_params": general_sim_params["general_link_params"]
        },
        'data_rates_params' : None, # simulation.params['data_rates_params'],   # now from recalculateLinkDatarates()
        'sim_run_params'    : { 
            "start_utc_dt" : tt.iso_string_to_dt(scenario_params['start_utc']),
            "end_utc_dt"   : tt.iso_string_to_dt(scenario_params['end_utc']) 
        },
        'sat_config'        : {
            'sat_model_definition':sat_model_definition # simulation.params['sat_config'],  # 'sat_model_definition' : data['sat_ref_model']['sat_model_definition']
        },
        'sim_gen_config'    : general_sim_params,                       # simulation.params['sim_gen_config'],
        'gp_general_params' : tmp_global_of_caseSpecificParams['gp_general_params']  # carrying over from initial setup
    }

    return params



def processWholesaleUpdate(caseSpecificParams):
    print("Updating tmp_global_of_caseSpecificParams!")
    global tmp_global_of_caseSpecificParams
    global parameter_updates
    global server


    #  if  caseSpecificParams  doens't have full content, or has a path to config
    if 'LOCAL_LOAD_PATH' in caseSpecificParams.keys():
        tmp_global_of_caseSpecificParams = loadFromLocalConfig(case_name=caseSpecificParams['LOCAL_LOAD_PATH']) if caseSpecificParams['LOCAL_LOAD_PATH'] is not None else loadFromLocalConfig()
    else:
        tmp_global_of_caseSpecificParams = DotDict(caseSpecificParams)


    # tmp_global_of_caseSpecificParams.pop("data_rates_params")                     # Forcing in-house [live] computation    
    # tmp_global_of_caseSpecificParams['orbit_prop_params'].pop("orbit_prop_data")  # Forcing in-house [live] computation    


    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_ids"] = tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params"][0]["sat_ids"]  # Moving the authoritative source - TODO: Validate all are equiv, if multiple given throughout.
    parameter_updates = { key:{
            'kepler_meananom' : [ elem["kepler_meananom"] for elem in tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_orbital_elems"] if elem['sat_id']==key ][0]  # only one result should match, get its keps; TODO: protect against no matches & pattern-type defs
        } for key in tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"] }  # empty dict, one for each sat ID
    print("Loaded scenario_params ({} KB).".format(round(len(pkl.dumps(tmp_global_of_caseSpecificParams))/1024)))

    assert( len([ elem["def_type"] for elem in tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_orbital_elems"] if elem["def_type"]!="indv" ]) == 0 ) # Satellites must be individually defined to use this part of the system (or ambiguity arises when live updates arrive) 


    repropagateSats()
    recalculateLinkDatarates()
    updateWindows()

    if server.act_timing_helper is None:
        server.act_timing_helper = ActivityTimingHelper(
            tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]['activity_params'], # self.sat_params['activity_params'],
            tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_ids_by_orbit_name"], #orbit_params['sat_ids_by_orbit_name'],
            tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"], # self.sat_params['sat_id_order'],
            None) 

    if server.plan_db is None:
        server.plan_db = PlanningInfoDB(
            tmp_global_of_caseSpecificParams['sim_run_params']['start_utc_dt'], # sim_start_dt,
            tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt'], # sim_end_dt,
            tmp_global_of_caseSpecificParams['sim_case_config']['sim_gsn_ID'],
            server.act_timing_helper # act_timing_helper
        )


    server.plan_db.sim_start_dt = tmp_global_of_caseSpecificParams['sim_run_params']['start_utc_dt']
    server.plan_db.sim_end_dt   = tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt']
    # Each update should refresh this, anyway
    ecl_winds_by_sat_id = {tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"][sat_indx]:all_windows_dict['ecl_winds'][sat_indx] for sat_indx in range(tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"])}
    
    server.plan_db.initialize({
        "sat_id_order": tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"], # self.sat_id_order,
        "gs_id_order" : tmp_global_of_caseSpecificParams["orbit_prop_params"]["gs_params"]["gs_id_order"], #self.gs_id_order,
        "other_agent_ids": [tmp_global_of_caseSpecificParams['sim_case_config']['sim_gsn_ID']], # [gsn_id],
        "initial_state_by_sat_id": tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["initial_state_by_sat_id"], # self.sat_params['initial_state_by_sat_id'],
        "ecl_winds_by_sat_id": ecl_winds_by_sat_id,
        "power_params_by_sat_id": tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params_by_sat_id"], # self.sat_params['power_params_by_sat_id'],
        "resource_delta_t_s": tmp_global_of_caseSpecificParams['sim_gen_config']['timestep_s'] #self.sim_run_params['sim_tick_s']
    })


SatStateEntry = namedtuple('SatStateEntry','update_dt state_info') # from sim_agent_components.py
# A set of state history for each telemetry aspect, the last of which is the most recent. 
def updateSatState(sat_id, sat_state):
    # TODO - validate expected formats
    # # Expected input example:
    # sat_state = {
    #     "power" : [ SatStateEntry(update_dt=tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt']-timedelta(minutes=1), state_info={"batt_e_Wh":12-1, "sat_id_prefix":"S", "sat_id":"S0"} ),
    #                 SatStateEntry(update_dt=tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt']-timedelta(minutes=2), state_info={"batt_e_Wh":12-2, "sat_id_prefix":"S", "sat_id":"S0"} ) ],
    #     "data"  : [ SatStateEntry(update_dt=tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt']-timedelta(minutes=1), state_info={"DS_state":500000} ),
    #                 SatStateEntry(update_dt=tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt']-timedelta(minutes=2), state_info={"DS_state":400000} ) ],
    #     "orbit" : [ SatStateEntry(update_dt=tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt']-timedelta(minutes=1), state_info={"a_km"        : 7378,
    #                                                                                                                                                     "e"           : 0,
    #                                                                                                                                                     "i_deg"       : 97.86,
    #                                                                                                                                                     "RAAN_deg"    : 0,
    #                                                                                                                                                     "arg_per_deg" : 0,
    #                                                                                                                                                     "M_deg"       : 180+5
    #                                                                                                                                                     } ),
    #                 SatStateEntry(update_dt=tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt']-timedelta(minutes=2), state_info={"a_km"        : 7378,
    #                                                                                                                                                     "e"           : 0,
    #                                                                                                                                                     "i_deg"       : 97.86,
    #                                                                                                                                                     "RAAN_deg"    : 0,
    #                                                                                                                                                     "arg_per_deg" : 0,
    #                                                                                                                                                     "M_deg"       : 180+10
    #                                                                                                                                                     } ) 
    #                 ]
    # }
    if type(sat_state['power'][0][0]) != str:
        powerState = sat_state['power']   # history to append before archiving (since last update)
                                                        # list of SatStateEntry(update_dt=telem_dt, state_info=loggedState)
                                                        # [oldest, ..., most recent]
        dataState  = sat_state['data']    # modeling after power (same as above), less the extra sat ID & such
        orbitState = sat_state['orbit']   # list of SatStateEntry(update_dt=telem_dt, state_info={
                                                                                                #     "a_km"        : 7378,
                                                                                                #     "e"           : 0,
                                                                                                #     "i_deg"       : 97.86,
                                                                                                #     "RAAN_deg"    : 0,
                                                                                                #     "arg_per_deg" : 0,
                                                                                                #     "M_deg"       : 180
                                                                                                # } )
        # attitudeState = sat_state['att']  # TODO: Attitude
    else:  # if coming from a pure json encoding, convert string representation to datetimes
        powerState = [ SatStateEntry(update_dt=tt.iso_string_to_dt(e[0]), state_info=e[1]) for e in sat_state['power'] ]
        dataState  = [ SatStateEntry(update_dt=tt.iso_string_to_dt(e[0]), state_info=e[1]) for e in sat_state['data']  ]
        orbitState = [ SatStateEntry(update_dt=tt.iso_string_to_dt(e[0]), state_info=e[1]) for e in sat_state['orbit'] ]

    global server

    if len(powerState) > 0:
        server.plan_db.sat_state_hist_by_id[sat_id] = [ entry for entry in server.plan_db.sat_state_hist_by_id[sat_id] if entry.update_dt < powerState[0].update_dt ] + powerState

    global parameter_updates
    if len(dataState) > 0 and 'data_state_Mb' in parameter_updates[sat_id].keys() > 0:
        # consider update series the truth (on board); all previous entries which fall after its oldest are removed, and the new entries are appended
        parameter_updates[sat_id]['data_state_Mb'] = [ entry for entry in parameter_updates[sat_id]['data_state_Mb'] if entry.update_dt < dataState[0].update_dt ] + dataState


    global tmp_global_of_caseSpecificParams
    if len(orbitState) > 0:
        reprop = False
        if parameter_updates[sat_id]['kepler_meananom']!=orbitState[-1]: # TODO - judge if new & old are substantially diffent enough to reprop
            reprop = True
        parameter_updates[sat_id]['kepler_meananom'] = orbitState[-1]
        for elem in tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_orbital_elems"]:  # Assumes sats are indv defined (per assertion during init)
            if elem["sat_id"] == sat_id:
                elem["kepler_meananom"] = parameter_updates[sat_id]['kepler_meananom']

        if reprop:
            repropagateSats()
            recalculateLinkDatarates()
            updateWindows()



def addSat(satParams):
    global tmp_global_of_caseSpecificParams
    # if ( satParams["overall_data_timestamp"] > datetime.now() ):
    #     print("WARNING: Future data snapshot not yet allowed. Not adding ", satParams['sat_id'] )
    #     return
    if satParams['sat_id'] in tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"]:
        print("WARNING: {} already exists, consider using updateSatParams()".format(satParams['sat_id']) )
        return
    if tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_prefix"] != satParams['sat_id'][:len(tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_prefix"])]:
        print("WARNING: {} prefix does not match expected prefix.".format(satParams['sat_id']) )
        return


    ##### orbit_prop_params #####
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"] += 1
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_satellites"] = tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"]
    
    # Modify "duplicate,range_inclusive" lines to use correct upper bound on end
    sat_ids_pattern = tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_ids"][:tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_ids"].rfind(",")+1] + str(tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"]-1)
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_ids"] = sat_ids_pattern  # This will be the authoritative source; TODO - remove the below locations
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params"][0]["sat_ids"] = sat_ids_pattern
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["data_storage_params"][0]["sat_ids"] = sat_ids_pattern
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["initial_state"][0]["sat_ids"] = sat_ids_pattern


    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"].insert(satParams['sat_order_position'],satParams['sat_id'])

    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params_by_sat_id"][satParams['sat_id']] = satParams['power_params_instance']
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["data_storage_params_by_sat_id"][satParams['sat_id']] = satParams['data_storage_params_instance']
    tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["initial_state_by_sat_id"][satParams['sat_id']] = satParams['initial_state_instance']

    tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_ids_by_orbit_name"][satParams['orbit_id']].insert(satParams['orbit_order_pos'], satParams['sat_id'])
    parameter_updates[satParams['sat_id']]['kepler_meananom'] = [ elem["kepler_meananom"] for elem in tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_orbital_elems"] if elem['sat_id']==satParams['sat_id'] ][0]  # only one result should match, get its keps; TODO: protect against no matches  & pattern-type defs

    satParams['orbit_data_instance'].update({"sat_id": TEMP_translateSatIDs(satParams['sat_id'])}) # update returns none, so have to do this in two steps
    tmp_global_of_caseSpecificParams["orbit_prop_params"]['orbit_prop_data']['sat_orbit_data'].insert(satParams['sat_order_position'], satParams['orbit_data_instance'] )

def removeSat(satID):
    global tmp_global_of_caseSpecificParams

    ##### orbit_prop_params #####
    if satID in tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"]:
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"] -= 1
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_satellites"] = tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"]
        
        # Modify "duplicate,range_inclusive" lines to use correct upper bound on end
        sat_ids_pattern = tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params"][0]["sat_ids"][:tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params"][0]["sat_ids"].rfind(",")+1] + str(tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["num_sats"]-1)
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_ids"] = sat_ids_pattern  # This will be the authoritative source; TODO - remove the below locations
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params"][0]["sat_ids"] = sat_ids_pattern
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["data_storage_params"][0]["sat_ids"] = sat_ids_pattern
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["initial_state"][0]["sat_ids"] = sat_ids_pattern


        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_id_order"].remove(satID)

        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["power_params_by_sat_id"].pop(satID)
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["data_storage_params_by_sat_id"].pop(satID)
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["initial_state_by_sat_id"].pop(satID)

        # remove from orbit_params
        for orbitID in tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_ids_by_orbit_name"].keys():
            if satID in tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_ids_by_orbit_name"][orbitID]:
                tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_params"]["sat_ids_by_orbit_name"][orbitID].remove(satID)

        # remove from orbit_prop_data
        tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_prop_data"]["sat_orbit_data"] = [ sat_orbit_data for sat_orbit_data in tmp_global_of_caseSpecificParams["orbit_prop_params"]["orbit_prop_data"]["sat_orbit_data"] if sat_orbit_data['sat_id']!=TEMP_translateSatIDs(satID) ]



def repropagateSats():  # TODO - signal which sat (when updated ephemeris is had) for efficiency
    global tmp_global_of_caseSpecificParams
   
    prop_input_data = {
        "sim_case_config" : {
            "scenario_params" : {
                "start_utc" : tmp_global_of_caseSpecificParams["sim_case_config"]["scenario_params"]["start_utc"], # tt.date_string( tmp_global_of_caseSpecificParams['sim_run_params']['start_utc_dt'] ),
                "end_utc"   : tmp_global_of_caseSpecificParams["sim_case_config"]["scenario_params"]["end_utc"], # tt.date_string( tmp_global_of_caseSpecificParams['sim_run_params']['end_utc_dt'] ),
                "use_crosslinks" : tmp_global_of_caseSpecificParams["sim_case_config"]["scenario_params"]["use_crosslinks"],
                "all_sats_same_time_system" : tmp_global_of_caseSpecificParams["sim_case_config"]["scenario_params"]["all_sats_same_time_system"]
            }
        },
        "sim_general_config" : {
            "general_sim_params" : {
                "timestep_s" : tmp_global_of_caseSpecificParams['sim_gen_config']['timestep_s'],
                "matlab_verbose" : tmp_global_of_caseSpecificParams['sim_gen_config']["matlab_verbose"],
                "include_ecef_output" : tmp_global_of_caseSpecificParams['sim_gen_config']["include_ecef_output"]
            }
        },
        "constellation_config" : {
            "constellation_definition" : {
                "constellation_params" : {
                    "num_satellites":tmp_global_of_caseSpecificParams['orbit_prop_params']["sat_params"]["num_satellites"],
                    "sat_id_prefix":tmp_global_of_caseSpecificParams['orbit_prop_params']["sat_params"]["sat_id_prefix"],
                    "sat_id_order":tmp_global_of_caseSpecificParams['orbit_prop_params']["sat_params"]["sat_id_order"],
                    "orbit_params":tmp_global_of_caseSpecificParams['orbit_prop_params']["orbit_params"]    # TODO - augment this part to handle non-ind. definitions
                }
            }
        },
        "gs_network_config" : {
            "network_definition" : {
                "gs_net_params" : {
                    "gs_network_name" : tmp_global_of_caseSpecificParams["orbit_prop_params"]["gs_params"]["gs_network_name"],
                    "stations"        : tmp_global_of_caseSpecificParams["orbit_prop_params"]["gs_params"]["stations"],
                    "elevation_cutoff_deg" : tmp_global_of_caseSpecificParams["orbit_prop_params"]["gs_params"]["elevation_cutoff_deg"],
                }
            }
        },
        "ops_profile_config" : {
            "ops_profile_params" : {
                "obs_params" : {
                    "target_set_name"       : tmp_global_of_caseSpecificParams["orbit_prop_params"]["obs_params"]["target_set_name"],
                    "elevation_cutoff_deg"  : tmp_global_of_caseSpecificParams["orbit_prop_params"]["obs_params"]["elevation_cutoff_deg"],
                    "targets"               : tmp_global_of_caseSpecificParams["orbit_prop_params"]["obs_params"]["targets"]
                }
            }
        },
        "cached_accesses_inputs" : None
    }

    output = runner_orbitprop.runOrbitProp(prop_input_data)
    tmp_global_of_caseSpecificParams['orbit_prop_params']["orbit_prop_data"] = output



def recalculateLinkDatarates():
    global tmp_global_of_caseSpecificParams

    link_input_data = {
        "sim_case_config" : {
            "scenario_params" : {
                "start_utc" : tt.date_string( tmp_global_of_caseSpecificParams['sim_run_params']['start_utc_dt'] ),
                "lookup_params" : tmp_global_of_caseSpecificParams['sim_case_config']['scenario_params']['lookup_params']
            }
        },
        "orbit_prop_data" : tmp_global_of_caseSpecificParams['orbit_prop_params']['orbit_prop_data'],
        'constellation_config' : {
            "constellation_definition" : {
                "constellation_params" : {
                    "num_satellites": tmp_global_of_caseSpecificParams['orbit_prop_params']['sat_params']['num_satellites'],
                    "sat_id_prefix":  tmp_global_of_caseSpecificParams['orbit_prop_params']['sat_params']['sat_id_prefix'],
                    "sat_ids":        tmp_global_of_caseSpecificParams["orbit_prop_params"]["sat_params"]["sat_ids"],
                    "sat_id_order":   tmp_global_of_caseSpecificParams['orbit_prop_params']['sat_params']['sat_id_order']  # a real test vs 'default'!
                }
            }
        },
        'gs_network_config' : {
            "network_definition" : {
                "gs_net_params" : {
                    "num_stations": len(tmp_global_of_caseSpecificParams["orbit_prop_params"]["gs_params"]["stations"]),
                    "stations":         tmp_global_of_caseSpecificParams["orbit_prop_params"]["gs_params"]["stations"]
                }
            }
        },
        'ops_profile_config' : {
            "ops_profile_params" : {
                "obs_params" : {
                    "num_targets" : len(tmp_global_of_caseSpecificParams["orbit_prop_params"]["obs_params"]["targets"]),
                },
                "link_disables" : {
                    "dlnk_direc_disabled_gs_ID_by_sat_IDstr":   tmp_global_of_caseSpecificParams["orbit_link_params"]["link_disables"]["dlnk_direc_disabled_gs_ID_by_sat_IDstr"],
                    "xlnk_direc_disabled_xsat_ID_by_sat_IDstr": tmp_global_of_caseSpecificParams["orbit_link_params"]["link_disables"]["xlnk_direc_disabled_xsat_ID_by_sat_IDstr"]
                }
            }
        },
        'sim_general_config' : {
            "general_sim_params" : {
                "general_link_params" : tmp_global_of_caseSpecificParams["orbit_link_params"]["general_link_params"]
            }
        },
        'sat_config' : tmp_global_of_caseSpecificParams['sat_config']
    }

    output = simple_link_calc.py_links_wrapper(link_input_data)
    tmp_global_of_caseSpecificParams['data_rates_params'] = output[0]



# TODO - modify the preprocessor to rectify prefixes
def TEMP_translateSatIDs(satID):
    if satID[0]=="S":
        return "sat"+satID[1:]
    elif len(satID) > 3 and satID[0:3]=="sat":
        return "S"+satID[3:]
    else:
        print("Translation not implemented")
        return satID

if __name__ == "__main__":
    main()