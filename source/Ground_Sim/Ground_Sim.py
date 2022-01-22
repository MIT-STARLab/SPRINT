from datetime import timedelta
from collections import OrderedDict
import pickle
import json
import os
import queue
from copy import copy, deepcopy
from circinus_tools.scheduling.io_processing import SchedIOProcessor
from circinus_tools.scheduling.custom_window import   ObsWindow,  DlnkWindow, XlnkWindow
from circinus_tools  import time_tools as tt
from circinus_tools.metrics.metrics_calcs import MetricsCalcs
from circinus_tools.plotting import plot_tools as pltl
import circinus_tools.metrics.metrics_utils as met_util
from circinus_tools  import io_tools
from circinus_tools.activity_bespoke_handling import ActivityTimingHelper
from circinus_sim.constellation_sim_tools.sim_agents import SimGroundNetwork,SimGroundStation
from circinus_sim.constellation_sim_tools.gp_wrapper import GlobalPlannerWrapper
from circinus_sim.constellation_sim_tools.sim_plotting import SimPlotting
from Ground_Sim.Ground_Server import GroundServer
from Ground_Sim.Ground_Client import GroundClient
from circinus_sim.constellation_sim_tools.Transmission_Simulator import Transmission_Simulator
from sprint_tools.Constellation_STN import Constellation_STN
import logging
from sprint_tools.Sprint_Types import AgentType
from Removed_Satellite.BlockingDict import BlockingDict
from threading import Thread,Condition
from Removed_Satellite.Message_ID_Assigner import MessageIDAssigner
import multiprocessing as mp
def print_verbose(string,verbose=False):
    if verbose:
        print(string)


class GroundSim:
    """
    easy interface for running the global planner scheduling algorithm and simulating ground-based components only
    
    Communicates using server/client protocol with satellites on separate devices
    """
    SAT_SERVER_PORT = 54200
    GROUND_SERVER_PORT = 54201
    VERBOSE = True
    
    def __init__(self, sim_params):
        """initializes based on parameters

        initializes based on parameters
        :param sim_params: global namespace parameters created from input files
                           (possibly with some small non-structural modifications to params).
                           The name spaces here should trace up all the way to the input files.
        :type params: dict
        """
        self.params = sim_params
        self.GPhotstart = self.params['sim_case_config']['sat_schedule_hotstart']
        self.sat_params = self.params['orbit_prop_params']['sat_params']

        self.orbit_params = self.params['orbit_prop_params']['orbit_params']
        self.gs_params = self.params['orbit_prop_params']['gs_params']
        self.const_sim_inst_params = sim_params['const_sim_inst_params']
        self.sim_run_params = sim_params['const_sim_inst_params']['sim_run_params']
        self.sim_run_perturbations = sim_params['const_sim_inst_params']['sim_run_perturbations']
        self.num_sats = self.sat_params['num_sats']
        self.sat_id_order = self.sat_params['sat_id_order']
        self.gs_id_order = self.gs_params['gs_id_order']
        self.obs_target_id_order = self.params['orbit_prop_params']['obs_params']['obs_target_id_order']
        self.num_gs = len(self.gs_params['gs_id_order'])
        
        self.restore_pickle_cmdline_arg = sim_params['restore_pickle_cmdline_arg']

        self.gs_id_ignore_list= self.params['gp_general_params']['other_params']['gs_id_ignore_list']

        self.sim_tick = timedelta(seconds=self.sim_run_params['sim_tick_s'])

        self.sim_start_dt = self.sim_run_params['start_utc_dt']
        self.sim_end_dt = self.sim_run_params['end_utc_dt']

        self.io_proc =SchedIOProcessor(self.params)
        self.sim_plotter = SimPlotting(self.params)
        
        assert sim_params["ground_sim"] # must be true
        
        ##### Server/Client Related params ######
        self.messagesToPass = {}
        self.msgIDAssigner = MessageIDAssigner()
        self.conn_to_server,self.server_conn = self.get_pipe_connections()
        self.server_proc = None
        self.client = self.set_up_client()

        ##### Message-related recording
        self.idsToMsgType = {}
        self.idsToTarget = {}
        self.idsToSender  = {}
        self.msgTypeToIDs = {"STATES":set(),"PLAN":set(),"BDT":set(),"PLAN_PROP":set(),"SAT_STATS":set()}

        self.responses = BlockingDict()
        self.join_msgs = queue.Queue()

        ##### Simulation-related flags ######
        self.numFinishedActs         = 0     # Number of peers done sending executive acts
        self.numReadyForUpdate       = 0     # Number of peers ready for state update
        self.numFinishedProp         = 0     # Number of peers done with plan propagation
        self.numReadyForNextTimeStep = 0     # Number of peers ready for next step
        self.numPeers = self.num_sats

        self.sim_lock = Condition()

        self.sat_stats = {id: None for id in self.sat_id_order} # Map of satellite stats. Used for post run
        self.postRunData = {id: None for id in self.sat_id_order}

        # we create a gp wrapper here, because:
        # 1. it's easy to give it access to sim params right now
        # 2. we want to store it in the constellation sim context, as opposed to within the gs network.
        #    It stores a lot of input data (e.g. accesses, data rates inputs...) and we don't want to be
        #    pickling/unpickling all that stuff every time we make a checkpoint in the sim. Note that
        #    the gp_wrapper does not internally track any constellation state, on purpose
        self.gp_wrapper = GlobalPlannerWrapper(self.params)

        # metrics calculation
        self.mc = MetricsCalcs(self.get_metrics_params())
        
        orbit_params = self.params['orbit_prop_params']['orbit_params']
        self.act_timing_helper = ActivityTimingHelper(self.sat_params['activity_params'],orbit_params['sat_ids_by_orbit_name'],self.sat_params['sat_id_order'],None)
        
        ##### Simulation State Truth #####
        stn_params = {
            'element_id_by_index': {
                'sat_id_by_indx'    : sim_params['orbit_prop_params']['sat_params']['sat_id_order'],
                'gs_id_by_indx'     : sim_params['orbit_prop_params']['gs_params' ]['gs_id_order'],
                'trget_id_by_indx'  : sim_params['orbit_prop_params']['obs_params']['obs_target_id_order']
            },
            'accesses_data' : sim_params['orbit_prop_params']['orbit_prop_data']['accesses_data']
        }
        self.access_truth_stn = Constellation_STN(stn_params)
        self.schedule_disruptions = self.params['sim_case_config']['sim_run_perturbations']['schedule_disruptions']

        #####  End Sim State Truth   #####

        self.Transmission_Simulator = Transmission_Simulator(False,False, self, removed_sat = True)

        self.CurGlobalTime = 0  # essentially not init

    def get_pipe_connections(self):
        """
        Creates connection between Ground Sim and its server.
        This connection spans multiple processes.
        """
        parent, child = mp.Pipe()
        return parent, child

    def set_up_client(self):
        """
        Creates client with no addresses
        """
        return GroundClient(self.messagesToPass)

    def run_server(self,conn:mp.connection.Connection):
        p = mp.Process(target = GroundServer,args=(self.GROUND_SERVER_PORT,self.num_sats,conn),daemon=True)
        p.start()
        return p


    def initialize_sats(self):
        """
        initialize satellite clients with parameters after client joins
        
        """
        ####### GENERAL STARTING SATELLITE PARAMETERS #######
        sat_id_sim_satellite_params = self.const_sim_inst_params['sim_satellite_params']
        
        sat_client_initialization_params = {"req_type":"INIT_PARAMS","payload":{},"waitForReply":True,"sender":"ground"}
        sat_client_initialization_params["payload"] = {"sat_id_sim_satellite_params": sat_id_sim_satellite_params,
                                                       "sim_start_dt": self.sim_start_dt,
                                                       "sim_end_dt": self.sim_end_dt,
                                                       "sim_params": self.params,
                                                       "activity_params": self.sat_params["activity_params"],
                                                       "sat_ids_by_orbit_name": self.orbit_params['sat_ids_by_orbit_name'],
                                                       "sat_id_order": self.sat_params['sat_id_order']
                                                       }

        satellite_list = list(enumerate(self.sat_id_order))
        i = 0
        ip_addresses = {}
        while i < self.num_sats: # Must initialize ALL sats to continue
            sat_index, sat_id = satellite_list[i]
            # ======================== Get id-specific parameters =========================
            
            # these params come from orbit prop inputs file
            sat_id_scenario_params = {
                "power_params": self.sat_params['power_params_by_sat_id'][sat_id],
                "data_storage_params": self.sat_params['data_storage_params_by_sat_id'][sat_id],
                "initial_state": self.sat_params['initial_state_by_sat_id'][sat_id],
                "activity_params": self.sat_params['activity_params']
            }
            
            sat_client_initialization_params["payload"]["sat_id_scenario_params"] = sat_id_scenario_params
            sat_client_initialization_params["payload"]["sat_id"] = sat_id
            sat_client_initialization_params["payload"]["sat_index"] = sat_index
            

            # ======================== Wait for satellite to join ========================
            msg = self.join_msgs.get() # Guaranteed to be a join message only until ALL satellites have joined

            msg_id = msg['id']
            assert msg['req_type'] == 'JOIN', 'Disallowed message type. Simulation ' \
                                              'unable to run until all satellites have joined'
            
            sat_address = msg['payload']['address']
            sat_port = msg['payload']['port']

            # check that client requests to "JOIN" before registering it
            if (sat_address,sat_port) not in ip_addresses.values(): # satellites must have unique addresses
                self.client.add_id(sat_id,sat_address,sat_port)
                ip_addresses[sat_id] = (sat_address,sat_port)
                # ======================== Send satellite parameters ========================
                self.sendResponse(msg_id,sat_id,True,msg['waitForReply'])
                successfulJoin = self.send_message(sat_client_initialization_params,target_id=sat_id)

                if not successfulJoin:
                    self.client.remove_id(sat_id)
                    ip_addresses[sat_id] = None # "delete" satellite from sim.
                else:
                    i += 1 # Successful joining. Move onto next id
        # ======================== Send satellite IP addresses ========================

        ip_msg = {"req_type":"ALL_IPS","payload":ip_addresses,"waitForReply":True,"sender":"ground"}
        self.send_message(ip_msg,broadcast = True)

    def getResponse(self,_id:str):
        """
        Gets the response from sending input message
        :param _id: The ID of the message sent
        :return: True if message sent successfully, False otherwise.
                If there is additional payload, sends the payload instead
        """
        return self.responses.get(_id)

    def sendResponse(self,_id:str, target:str, ack:bool, txWaitForReply:bool,response:dict = None):
        """
        Sends response for a message
        :param _id:             The ID of the message to respond to
        :param target:          The ID of the sending agent
        :param ack:             True if acknowledged, false otherwise
        :param txWaitForReply:  True if tx is actively waiting for a reply
        :param response: (If any) additional response data
        """
        response = {"ACK":ack, "payload": response,"id":_id,"waitForReply":False,'txWaitForReply':txWaitForReply}
        self.send_message(response,target_id = target)
        
    def send_message(self,message:dict,target_id:str = None, broadcast:bool = False):
        """
        Sends message to satellite using pickle serialization
          Must have either sat_id defined or broadcast = True
        
        :param message      The dictionary to send
        :param target_id    The ID of the satellite
        :param broadcast    True if sending to ALL satellites, False otherwise
        :return             True if successful, False if not
        
        Message sent successfully if entire message sent and an acknowledgement message received
        """
        assert target_id or broadcast, "sat_id must be defined or broadcast must be true"

        isACK = True if 'ACK' in message else False

        ids = set()

        if target_id:
            message['dest'] = target_id
            if not isACK:
                msgId = self.msgIDAssigner.assign_id()
                ids.add(msgId)
                message['id'] = msgId
            else:
                msgId = message['id']

            self.messagesToPass[target_id].put(message)

        elif broadcast:
            idsToUse = self.msgIDAssigner.assign_ids(self.numPeers)
            ids.update(idsToUse)

            for peer in self.messagesToPass:
                peerMessage = message.copy()
                peerMessage['dest'] = peer
                peerMessage['id'] = idsToUse.pop()
                msgType = peerMessage['req_type']
                self.messagesToPass[peer].put(peerMessage)

        waitForReply = message['waitForReply']

        if waitForReply:
            # Check all recipients for broadcast
            if broadcast:
                assert not isACK
                success = True
                for _id in ids:
                    success = success and self.getResponse(_id)
                return success
            else:
                if not isACK:
                    msgType = message['req_type']
                else:
                    msgType = 'ACK'

                if not isACK:
                    return self.getResponse(msgId)


        else:
            # Record message type and ID to process responses later
            if not isACK:
                msgType = message['req_type']
                # print("<MAIN> assigning {} to {}".format(msgType,msgId))
                if msgType == 'PLAN' and message['plan_prop']:
                    msgType = 'PLAN_PROP'

                for _id in ids:
                    self.idsToMsgType[_id] = msgType
                    self.idsToTarget[_id] = target_id
                    self.idsToSender[_id]  = message['sender']
                self.msgTypeToIDs[msgType].update(ids)

            else:
                pass

    
    def handle_message(self,message:dict):
        """
        Handles in-simulation message based on message type. Responds with appropriate
        response messages

        Assumes message is valid.

        @param message              The message to handle, deserialized

        """
        
        messageType = message["req_type"]
        key = message['id']
        target = message['sender']

        dest = message['dest'] if 'dest' in message else 'ground'

        if messageType in {'PLAN','BDT','STATES'} and dest in self.gs_id_order:
            
            responseData = self.receive_message(message)

            if messageType == "PLAN":
                # Handle new LP information if needed
                if message['handle_lp']:
                    self.handle_new_lp_info(message)

                if message['exchange']:
                    # Check if sender requests an exchange
                    # of PLAN messages
                    gs = self.gs_by_id[message['dest']]

                    with gs.lock:
                        new_time, dest = message['payload']['new_time'], message['sender']
                        info_option = message['payload']['info_option']
                        gs.get_plan_db().update_self_ttc_time(new_time)
                        responseData = gs.make_planning_message(dest,info_option=info_option)
                        respType = "PLAN"

            if messageType == 'BDT':
                print(f'BDT RESPONSE for {key}: {responseData}')

            self.sendResponse(key,target,True,message['waitForReply'],responseData)

        else:
            with self.sim_lock:
                if messageType == 'ACTS_DONE':
                    self.numFinishedActs += 1
                    self.sendResponse(key, target,True,message['waitForReply'])
                    if self.numFinishedActs == self.numPeers:
                        self.sim_lock.notifyAll()

                elif messageType == 'FINISHED_PROP':
                    self.numFinishedProp += 1
                    self.sendResponse(key, target,True,message['waitForReply'])
                    if self.numFinishedProp == self.numPeers:
                        self.sim_lock.notifyAll()

                elif messageType == 'READY_FOR_TIME_UPDATE':
                    self.numReadyForNextTimeStep += 1
                    self.sendResponse(key, target,True,message['waitForReply'])
                    if self.numReadyForNextTimeStep == self.numPeers:
                        self.sim_lock.notifyAll()

                elif messageType == 'SAT_STATS':
                    sender = message['sender']
                    self.sat_stats[sender] = message['payload']
                    self.sendResponse(key, target,True,message['waitForReply'])
                    if all(self.sat_stats.values()):
                        self.sim_lock.notifyAll()

                elif messageType == 'POST_RUN':
                    sender = message['sender']
                    payload = message['payload']
                    self.postRunData[sender] = payload
                    self.sendResponse(key, target,True,message['waitForReply'])
                    
                    if all(self.postRunData.values()):
                        self.sim_lock.notifyAll()

                else:
                    print("WARNING: Unknown message type.")
                    self.sendResponse(key, target,False,message['waitForReply'])

    def receive_message(self,message:dict):
        """
        Receives message by redirecting it to the relevant ground station
        :param message: The input message to receive
        :return: Any response data
        """
        sender_id = message['sender']
        assert sender_id in self.sat_id_order, "Unknown satellite id {}".format(sender_id)
        
        dest_id = message['dest']
        assert dest_id in self.gs_by_id.keys(), "Unknown destination id {}".format(dest_id)

        gs_dest = self.gs_by_id[dest_id]
        x = gs_dest.receive_message(message)
        return x

    def handleResponse(self,response:dict):
        """
        Handles delayed received response for PLAN, STATES, AND BDT

        For PLAN_PROP:
            - Updates the last time the sender satellite has been updated
        For STATES:
            - Checks which applicable satellites have not ACKED (or have ACKED)
            - Updates the last time of satellite broadcast
        For BDT:
            - Updates ACKed BDT statements, essential for SRP

        :param response: The response

        """
        # Get original sent message information
        msgId = response[1]
        waitForReply = response[3]


        if waitForReply:
            self.responses.put(msgId, response[2])
            return

        msgType = self.idsToMsgType.pop(msgId)
        original_target = self.idsToTarget.pop(msgId)
        original_sender = self.idsToSender.pop(msgId)

        # Access the applicable GS
        gs = self.gs_by_id[original_sender]

        # Remove the ACKed ID from the nonACKed IDs list
        idsToTrack = self.msgTypeToIDs[msgType]
        idsToTrack.remove(msgId)
        # print("<MAIN> ids To track:", idsToTrack)
        # print("<MAIN> removed msgId {} from idsToTrack".format(msgId))

        if 'PLAN' in msgType:
            if msgType == 'PLAN_PROP':
                gs.stats['plan_uplinks_succeded'] += 1
                self.gs_network.mark_sat_updated(original_target,tt.datetime2mjd(self.CurGlobalTime))

            if type(response[2]) == dict:
                self.receive_message(response[2])
        else:
            pass

        
    def handle_new_lp_info(self,message:dict):
        """
        Handles incoming new LP info from a satellite given the <message> by
        updating next window uids if necessary
        
        :param message      The message sent
        """

        with self.gs_network.lock:
            # Get information about sender
            sender_id = message['sender']
            assert sender_id in self.sat_id_order, "Unknown satellite id {}".format(sender_id)

            sender_index = self.sat_id_order.index(sender_id)

            # Update windows, if necessary
            scheduleDisruptionCommunicated = message['payload']['schedule_disruption_replan_communicated']

            if not scheduleDisruptionCommunicated:
                update_keys = ['dlnk_winds','dlnk_winds_flat']
                sat_windows_dict = message['payload']['sat_windows_dict']

                for key in update_keys:
                    self.gs_network.scheduler.all_windows_dict[key][sender_index] = sat_windows_dict[key]

                sat_next_window_uid = sat_windows_dict['next_window_uid']
                current_next_window_uid = self.gs_network.scheduler.all_windows_dict['next_window_uid']

                if sat_next_window_uid > current_next_window_uid:
                    self.gs_network.scheduler.all_windows_dict['next_window_uid'] = sat_next_window_uid

                    msg = {'req_type': 'NEXT_WINDOW_UPDATE',
                           'payload' : sat_next_window_uid,
                           'sender'  : 'ground'
                            }

                    for other_sat_id in self.sat_id_order:
                        if other_sat_id != sender_id:
                            self.send_message(msg,other_sat_id)

            self.gsn_exchange_planning_info_all_exec_agents()
              
    def init_data_structs(self):
        """ initialize data structures used in the simulation """
        
        window_uid = -9999
        # ecl_winds is an array with index for each sat_indx
        ecl_winds, window_uid =self.io_proc.import_eclipse_winds(window_uid)
        if window_uid >= 0:
            raise RuntimeWarning('Saw positive window ID for ecl window hack')

        ecl_winds_by_sat_id = {self.sat_id_order[sat_indx]:ecl_winds[sat_indx] for sat_indx in range(self.num_sats)}
        self.ecl_winds = ecl_winds

        # create satellites
        self.initialize_sats()

        # create ground network
        gs_by_id = {}
        all_gs = []
        gsn_id = 'gsn'
        gs_network = SimGroundNetwork(
            gsn_id,
            self.gs_params['gs_network_name'],
            self.sim_start_dt,
            self.sim_end_dt,
            self.num_sats,
            self.num_gs,
            self.const_sim_inst_params['sim_gs_network_params'],
            self.act_timing_helper,
            self,
            {id: id for id in self.sat_id_order},
            self.access_truth_stn,   # Only in this deterministic case where it is known. Else use a filter of, etc.
            removed=True
        )
        #  note: use sim tick as resource delta T.
        plan_db_inputs = {
            "sat_id_order": self.sat_id_order,
            "gs_id_order" : self.gs_id_order,
            "other_agent_ids": [gsn_id],
            "initial_state_by_sat_id": self.sat_params['initial_state_by_sat_id'],
            "ecl_winds_by_sat_id": ecl_winds_by_sat_id,
            "power_params_by_sat_id": self.sat_params['power_params_by_sat_id'],
            "resource_delta_t_s": self.sim_run_params['sim_tick_s']
        }
        # Create ground stations
        for station in self.gs_params['stations']:
            gs = SimGroundStation(
                str(station['id']),
                self.gs_id_order.index(str(station['id'])),
                station['name'],
                gs_network,
                self.sim_start_dt,
                self.sim_end_dt,
                self.const_sim_inst_params['sim_gs_params'],
                self.act_timing_helper,
                self,
                self.schedule_disruptions,
                removed = True
            )
            gs_by_id[station['id']] = gs
            gs_network.gs_list.append(gs)
            all_gs.append(gs)

            #  initialize the planning info database
            gs.get_plan_db().initialize(plan_db_inputs)

        #  initialize the planning info database
        gs_network.get_plan_db().initialize(plan_db_inputs)
        self.gs_network = gs_network
        self.gs_by_id = gs_by_id

        self.inject_obs()
    def getReferenceByID(self,id:str):
        """
        Get GS object from the ID
        :param id: The ID of the GS to access
        :return The GS object with the input ID, else the GS network
        """
        return self.gs_by_id.get(id,self.gs_network)
    
    def getAgentType(self,id:str):
        """
        Get the agent type based on ID
        :param id: The ID of the Agent
        :return: The given agent type, with GSNET as default
        """
        if id in self.gs_by_id.keys(): return AgentType.GS
        elif id in self.sat_id_order: return AgentType.SAT
        return AgentType.GSNET
        
    def getAllGSIDs(self):
        """
        Gets all gs ids, ordered by index
        """
        return self.gs_id_order
        
    def getAllSatIDs(self):
        """
        Gets all satellite ids, ordered by index
        """
        return self.sat_id_order
        
    def inject_obs(self):
        """
        Injects observations into satellite schedules
        """
        
        inj_obs_raw = self.sim_run_perturbations['injected_observations']

        if not self.sim_run_perturbations['do_inject_obs']:
            return

        inj_obs_by_sat_id = {}
        for obs_raw in inj_obs_raw:
            if not obs_raw['type'] == 'hardcoded':
                raise NotImplementedError

            sat_id = obs_raw['sat_id']
            obs = ObsWindow(
                obs_raw['indx'],
                sat_indx= self.sat_id_order.index(sat_id),
                target_IDs=['inject_'+str(obs_raw['indx'])],
                sat_target_indx=0,
                start= tt.iso_string_to_dt (obs_raw['start_utc']),
                end= tt.iso_string_to_dt (obs_raw['end_utc']),
                wind_obj_type='injected'
            )

            # pretty hardcore hacky here, but things seem to do badly when injected obs have huge dv. Try it this way
            obs.data_vol = 300
            obs.original_data_vol = 300

            inj_obs_by_sat_id.setdefault(sat_id, []).append(obs)
        
        message = {'req_type': 'INJECT_OBS', 'sender':'ground','waitForReply':True}
        
        for sat_id in self.sat_id_order:
            message['payload'] = inj_obs_by_sat_id.get(sat_id,[])
            self.send_message(message,sat_id)

    def run_controller(self):
        """
        Run background controller to process incoming messages
        :return:
        """
        while True:
            msg = self.conn_to_server.recv()

            if type(msg) == dict:
                self.handle_message(msg)
            elif "ACK" == msg[0]:
                self.handleResponse(msg)
            elif 'ERROR' in msg[0]:
                print(msg[1])
            elif "JOIN" in msg[0]:
                self.join_msgs.put(msg[1])

    def run(self):
        """ run the simulation """
        logging.basicConfig(filename=(self.params['output_path']+'logs/sim_sats.log'),level=logging.DEBUG)

        self.server_proc = self.run_server(self.server_conn)

        # Run message processor in background
        t = Thread(target = self.run_controller)
        t.setDaemon(True)
        t.start()

        self.init_data_structs()
        
        verbose = True

        global_time             = self.sim_start_dt
        sim_end_dt              = self.sim_end_dt

        #  used to alert special operations on first iteration of the loop
        first_iter = True



        if first_iter:
            # Change from building all potential activity windows over the entire sim every time the GP is
            # ran to instead build them once at the start of sim
            # and then associate the relevant windows with the relevant planning objects
            # (GSN knows all windows, each satellite knows windows in which they can participate)
            # First: create the params input structure required by SchedIOProcessor

            if not self.gs_network.scheduler.outsource:
                io_proc = SchedIOProcessor(self.params)

                # Load all windows: .
                print_verbose('Load files',verbose)

                # parse the inputs into activity windows
                window_uid = 0
                print_verbose('Load obs',verbose)
                obs_winds, window_uid =io_proc.import_obs_winds(window_uid)
                print_verbose('Load dlnks',verbose)
                dlnk_winds, dlnk_winds_flat, window_uid =io_proc.import_dlnk_winds(window_uid)
                print_verbose('Load xlnks',verbose)
                xlnk_winds, xlnk_winds_flat, window_uid =io_proc.import_xlnk_winds(window_uid)

                # if crosslinks are not allowed to be used (in sim_case_config), then zero out all crosslink windows
                # NOTE: this is done here and not further upstream because the access windows
                # are used for calculating planning comms windows as well
                if not self.params['sim_case_config']['use_crosslinks']:
                    xlnk_winds = [[[]] * self.num_sats] * self.num_sats
                    xlnk_winds_flat = [[]] * self.num_sats # list of N_sats empty lists

                # note: this import is currently done independently from circinus constellation sim.
                # If we ever need to share knowledge about ecl winds between the two,
                # will need to make ecl winds an input from const sim
                print_verbose('Load ecl',verbose)
                ecl_winds, window_uid =io_proc.import_eclipse_winds(window_uid)

                # Note, they are only validated inside the GP (other_helper not imported here)
                """ print_verbose('Validate windows',verbose)
                other_helper.validate_unique_windows(self,obs_winds,dlnk_winds_flat,xlnk_winds,ecl_winds) """

                print_verbose('In windows loaded from file:',verbose)
                print_verbose('obs_winds',verbose)
                print_verbose(sum([len(p) for p in obs_winds]),verbose)
                print_verbose('dlnk_win',verbose)
                print_verbose(sum([len(p) for p in dlnk_winds]),verbose)
                print_verbose('xlnk_win',verbose)
                print_verbose(sum([len(xlnk_winds[i][j]) for i in  range( self.sat_params['num_sats']) for j in  range( self.sat_params['num_sats']) ]),verbose)

                # Make all windows knows to the GSN
                # Each entry into this dictionary (except next_window_uid) is a list of length num_sats, where
                # each index in the outer list corresponds to the satellite index.
                all_windows_dict = {
                    'obs_winds': obs_winds,
                    'dlnk_winds': dlnk_winds,
                    'dlnk_winds_flat': dlnk_winds_flat,
                    'xlnk_winds': xlnk_winds,
                    'xlnk_winds_flat': xlnk_winds_flat,
                    'ecl_winds': ecl_winds,
                    'next_window_uid': window_uid
                }

                self.gs_network.scheduler.all_windows_dict = all_windows_dict

            with self.gs_network.lock:
                # Parse out windows for each satellite, add them to the queue of info to be sent to that satellite
                for sat_index,sat_id in enumerate(self.sat_id_order):
                    # For immediate testing, just immediate set the information into their plan_db.

                    windows = {}
                    for key in self.gs_network.scheduler.all_windows_dict.keys():
                        if key != 'next_window_uid':
                            windows[key] = self.gs_network.scheduler.all_windows_dict[key][sat_index]
                        else:
                            windows[key] = self.gs_network.scheduler.all_windows_dict[key]

                    message = {"req_type": "SAT_WINDOWS_INIT","payload":deepcopy(windows),'waitForReply':True,'sender':'ground'}
                    self.send_message(message,sat_id)

  
                
        #######################
        # Simulation loop
        #######################

        while global_time < sim_end_dt:
            self.CurGlobalTime = global_time

            # ======================================================================
            # ======================== Activity Execution ==========================
            # ======================================================================

            #  execute activities at this time step before updating state to the next time step
            
            # If first iteration: Server broadcasts START
            if first_iter:
                start_message = {'req_type': 'START', 'payload': None, 'sender':'ground',"waitForReply":True}
                self.send_message(start_message,broadcast = True)


            # Note that ground stations do not currently do anything in the execution step.
            # Including for completeness/API coherence
            for gs in self.gs_by_id.values():
                gs.execution_step(global_time)


            # Wait for satellites to finish sending executive acts messages
            with self.sim_lock:
                self.sim_lock.wait_for(lambda: self.numFinishedActs == self.numPeers)
                self.numFinishedActs = 0

            # ======================================================================
            # =========================== State Update =============================
            # ======================================================================

            #  run ground network update step so that we can immediately share plans on first iteration of this loop
            self.gs_network.state_update_step(global_time,self.gp_wrapper)

            with self.sim_lock:
                # start all the satellites with a first round of GP schedules, if so desired
                if first_iter and self.GPhotstart:
                    self.Transmission_Simulator.setBackbone(True)       # Pair with set to false below

                    with self.gs_network.lock:
                        self.gsn_exchange_planning_info_all_exec_agents()

                    for gs in self.gs_by_id.values():
                        gs.plan_prop(self,tt.datetime2mjd(global_time),True)

                    self.Transmission_Simulator.setBackbone(False)

            finishedSendingActsMsg = {'req_type': 'ACTS_DONE','payload':None,'sender':'ground',"waitForReply":True}
            self.send_message(finishedSendingActsMsg,broadcast = True)

            # update ground station states
            for gs in self.gs_by_id.values():
                gs.state_update_step(global_time)

            # ======================================================================
            # ======================== Plans Info Sharing ==========================
            # ======================================================================
            with self.gs_network.lock:
                # whenever GP has run, share info afterwards
                # Satellites WAIT for the moment
                if self.gs_network.scheduler.check_external_share_plans_updated():
                    self.gsn_exchange_planning_info_all_exec_agents()

            # Groundstations share with sats if appropriate
            for gs in self.gs_by_id.values():
                gs.plan_prop(None,tt.datetime2mjd(global_time))


            finishedPropMsg = {'req_type': 'FINISHED_PROP', 'payload': None, 'sender': 'ground',"waitForReply":True}
            self.send_message(finishedPropMsg, broadcast=True)

            with self.sim_lock:
                self.sim_lock.wait_for(lambda: self.numFinishedProp == self.numPeers)
                self.numFinishedProp = 0

            readyForNextTimeStepMsg = {'req_type': 'READY_FOR_TIME_UPDATE', 'payload': None,
                                       'sender': 'ground',"waitForReply":True}
            self.send_message(readyForNextTimeStepMsg, broadcast=True)

            with self.sim_lock:
                self.sim_lock.wait_for(lambda: self.numReadyForNextTimeStep == self.numPeers)
                self.numReadyForNextTimeStep = 0

                for gs in self.gs_by_id.values():
                    gs.no_more_bdt = False

                self.gs_network.no_more_bdt = False
                global_time += self.sim_tick
                first_iter = False

            print("\n==================================================================")
            print("================ CURRENT TIME : {} ================".format(global_time))
            print("==================================================================\n")

        ####
        # end of sim

        with self.sim_lock:
            self.sim_lock.wait_for(lambda: all(self.sat_stats.values()))


        print("GS#: Uplinks / Attempts")
        for gs in self.gs_by_id.values():
            print("{}: {} / {}".format(gs.ID, gs.stats['plan_uplinks_succeded'], gs.stats['plan_uplinks_attempted']))

        print("\nSAT#: Plan Props / Attempts")
        for satID in self.sat_stats:

            planPropsSucceeded = self.sat_stats[satID]['plan_props_succeded']
            planPropsAttempted = self.sat_stats[satID]['plan_props_attempted']

            print("{}: {} / {}".format(satID, planPropsSucceeded, planPropsAttempted))

    def gsn_exchange_planning_info_all_exec_agents(self):
        """
        Simulate exchange of planning information between ground station network and
        rest of ground stations
        """
        #  every time the ground network re-plans, want to send that updated planning information to the ground stations
        for gs_id in self.gs_by_id.keys():

            self.gs_network.send_planning_info(gs_id,info_option='routes_only')
            self.gs_by_id[gs_id].send_planning_info(self.gs_network.ID,info_option='routes_only')

        self.gs_network.scheduler.set_external_share_plans_updated(False)
    
    def post_run(self, output_path):

        postRunReq = {'req_type': 'POST_RUN_REQ','payload':None,'sender':'ground',"waitForReply":True}
        self.send_message(postRunReq,broadcast=True)

        with self.sim_lock:
            self.sim_lock.wait_for(lambda: all(self.postRunData.values()))

        # get sats and gs in index order
        gs_in_indx_order = [None for gs in range(len(self.gs_by_id))]
        for gs in self.gs_by_id.values():
            gs_in_indx_order[gs.gs_indx] = gs


        # report events
        event_logs = OrderedDict()
        event_logs['sats'] = OrderedDict()
        event_logs['gs'] = OrderedDict()

        for sat_id in self.postRunData:
            event_logs['sats'][sat_id] = self.postRunData[sat_id]['event_logs']

        for gs in gs_in_indx_order:
            gs.state_recorder.log_event(self.sim_end_dt,'constellation_sim.py','final_dv',[str(dc) for dc in gs.state_sim.get_curr_data_conts()])
            event_logs['gs'][gs.ID] = gs.state_recorder.get_events()

        
        if not os.path.exists(output_path+'logs'):          # /outputs/plots
            if not os.path.exists(output_path):             # /outputs
                os.mkdir(output_path)
            os.mkdir(output_path+'logs')

        event_log_file = output_path+'logs/agent_events.json'
        with open(event_log_file,'w') as f:
            json.dump(event_logs, f, indent=4, separators=(',', ': '))


        # Get the activities executed for all the satellites
        obs_exe = [[] for indx in range(self.num_sats)]
        dlnks_exe = [[] for indx in range(self.num_sats)]
        gs_dlnks_exe = [[] for indx in range(self.num_gs)]
        xlnks_exe = [[] for indx in range(self.num_sats)]
        # Get activities that execute, but failed (dv_del/dv_sch doesn't meet threshold) for all satellites
        obs_exe_fail = [[] for indx in range(self.num_sats)]
        dlnks_exe_fail = [[] for indx in range(self.num_sats)]
        gs_dlnks_exe_fail = [[] for indx in range(self.num_gs)]
        xlnks_exe_fail = [[] for indx in range(self.num_sats)]
        energy_usage = {'time_mins': [[] for indx in range(self.num_sats)], 'e_sats': [[] for indx in range(self.num_sats)]}
        data_usage = {'time_mins': [[] for indx in range(self.num_sats)], 'd_sats': [[] for indx in range(self.num_sats)]}

        exec_failures_dicts_list = []
        non_exec_failures_dicts_list = []

        for sat_id in self.postRunData:

            sat_indx = self.sat_id_order.index(sat_id)
            acts_exe = self.postRunData[sat_id]['acts_exe']

            # Get actions related to executive acts
            obs_exe[sat_indx] = acts_exe['obs']
            dlnks_exe[sat_indx] = acts_exe['dlnk']
            xlnks_exe[sat_indx] = acts_exe['xlnk']

            failures_exec = self.postRunData[sat_id]['failures_exec']
            failures_nonexec = self.postRunData[sat_id]['failures_nonexec']

            # activities that failed (see failed_dict)
            all_failures_values = list(failures_exec.values()) + list(failures_nonexec.values())
            exec_failures_dicts_list.append({ **failures_exec})
            non_exec_failures_dicts_list.append({ **failures_nonexec })

            # Classify failures
            all_failures = [act for set_of_acts in all_failures_values for act in set_of_acts] # this list could have duplicates
            obs_exe_fail[sat_indx] = [act for act in all_failures if isinstance(act,ObsWindow) ]
            dlnks_exe_fail[sat_indx] = [act for act in all_failures if isinstance(act,DlnkWindow)]
            xlnks_exe_fail[sat_indx] = [act for act in all_failures if isinstance(act,XlnkWindow)]

            # Get energy usage data
            t,e = self.postRunData[sat_id]['energy_usage']
            energy_usage['time_mins'][sat_indx] = t
            energy_usage['e_sats'][sat_indx] = e

            # Get data usage data
            t,d = self.postRunData[sat_id]['data_usage']
            data_usage['time_mins'][sat_indx] = t
            data_usage['d_sats'][sat_indx] = d

        for gs in self.gs_by_id.values():
            gs_indx = gs.gs_indx
            acts_exe = gs.get_act_hist()
            # NOTE: failure recorder only implemented on sats for now
            # all_failures_values = list(gs.state_recorder.failed_dict['exec'].values()) + list(gs.state_recorder.failed_dict['non-exec'].values())
            # all_failures = [act for set_of_acts in all_failures_values for act in set_of_acts]
            gs_dlnks_exe[gs_indx] =  acts_exe['dlnk']
            # need to pull failed downlinks from the sat lists
            gs_dlnks_exe_fail[gs_indx] = [act for list_of_acts_by_sat in dlnks_exe_fail for act in list_of_acts_by_sat if act.gs_indx == gs_indx]

        #  get scheduled activities as planned by ground network
        obs_gsn_sched,dlnks_gsn_sched,xlnks_gsn_sched = self.gs_network.get_all_sats_planned_act_hists()
        gs_dlnks_gsn_sched = self.gs_network.get_all_gs_planned_act_hists()


        ##########
        # Run Metrics
        self.run_and_plot_metrics(energy_usage,data_usage,gs_in_indx_order,dlnks_exe,xlnks_exe,non_exec_failures_dicts_list)

        ##########
        # Plot stuff

        sats_to_plot = self.sat_id_order

        # Activity Failure vs. Data Storage Plot
        # goal is to plot over the data-state graph with each failure labeled with the DV_failed and failure_type (exec_failures)
        self.sim_plotter.sim_plot_all_sats_failures_on_data_usage(
            sats_to_plot,
            exec_failures_dicts_list,
            data_usage
        )

        #  plot scheduled and executed activities for satellites
        self.sim_plotter.sim_plot_all_sats_acts(
            sats_to_plot,
            obs_gsn_sched,
            obs_exe,
            dlnks_gsn_sched,
            dlnks_exe,
            xlnks_gsn_sched,
            xlnks_exe,
            sats_obs_winds_failed=obs_exe_fail,
            sats_dlnk_winds_failed=dlnks_exe_fail,
            sats_xlnk_winds_failed=xlnks_exe_fail
        )

        #  plot scheduled and executed down links for ground stations
        self.sim_plotter.sim_plot_all_gs_acts(
            self.gs_id_order,
            gs_dlnks_gsn_sched,
            gs_dlnks_exe,
            gs_dlnks_exe_fail
        )

        #  plot satellite energy usage
        self.sim_plotter.sim_plot_all_sats_energy_usage(
            sats_to_plot,
            energy_usage,
            self.ecl_winds
        )

        #  plot satellite data usage
        self.sim_plotter.sim_plot_all_sats_data_usage(
            sats_to_plot,
            data_usage,
            self.ecl_winds
        )

        return None

    def run_and_plot_metrics(self,energy_usage,data_usage,gs_in_indx_order,dlnks_exe,xlnks_exe,non_exec_failures_dicts_list = None):

        calc_act_windows = True
        if calc_act_windows:
            print('------------------------------')
            print('Potential DVs')
            print('Load obs')
            window_uid = 0  # note this window ID will not match the one for executed windows in the sim! These are dummy windows!
            obs_winds, window_uid =self.io_proc.import_obs_winds(window_uid)
            print('Load dlnks')
            dlnk_winds, dlnk_winds_flat, window_uid =self.io_proc.import_dlnk_winds(window_uid)
            print('Load xlnks')
            xlnk_winds, xlnk_winds_flat, window_uid =self.io_proc.import_xlnk_winds(window_uid)

            total_num_collectible_obs_winds = sum(len(o_list) for o_list in obs_winds)
            total_collectible_obs_dv = sum(obs.original_data_vol for o_list in obs_winds for obs in o_list)
            total_dlnkable_dv = sum(dlnk.original_data_vol for d_list in dlnk_winds_flat for dlnk in d_list)

            print('total_num_collectible_obs_winds: %s'%total_num_collectible_obs_winds)
            print('total_collectible_obs_dv: %s'%total_collectible_obs_dv)
            print('total_dlnkable_dv: %s'%total_dlnkable_dv)


        # data containers mark their data vol in their data routes with the "data_vol" attribute, not "scheduled_dv"
        def dc_dr_dv_getter(dr):
            return dr.data_vol

        # Get the planned dv for a route container. Note that this includes utilization rt_cont
        # it's the same code as the dc_dr one, but including for clarity
        def rt_cont_plan_dv_getter(rt_cont):
            return rt_cont.data_vol



        # get all the rt containers that the gs network ever saw
        planned_routes = self.gs_network.get_all_planned_rt_conts()
        planned_routes_regular = [rt for rt in planned_routes if not rt.get_obs().injected]
        planned_routes_injected = [rt for rt in planned_routes if rt.get_obs().injected]
        # get the routes for all the packets at each GS at sim end
        executed_routes_regular = [dc.executed_data_route for gs in self.gs_by_id.values() for dc in gs.get_curr_data_conts() if not dc.injected]

        executed_routes_injected = [dc.executed_data_route for gs in self.gs_by_id.values() for dc in gs.get_curr_data_conts() if dc.injected]

        # debug_tools.debug_breakpt()

        # note that the below functions assume that for all rt_conts:
        # - the observation, downlink for all DMRs in the rt_cont are the same

        print('------------------------------')

        dv_stats = self.mc.assess_dv_by_obs(
            planned_routes_regular, executed_routes_regular,
            rt_poss_dv_getter=rt_cont_plan_dv_getter, rt_exec_dv_getter=dc_dr_dv_getter, verbose = True)

        print('injected dv')
        inj_dv_stats = self.mc.assess_dv_by_obs(
            planned_routes_injected, executed_routes_injected,
            rt_poss_dv_getter=rt_cont_plan_dv_getter, rt_exec_dv_getter=dc_dr_dv_getter ,verbose = True)


        print('------------------------------')
        lat_stats = self.mc.assess_latency_by_obs(planned_routes_regular, executed_routes_regular, rt_exec_dv_getter=dc_dr_dv_getter ,verbose = True)

        print('injected latency')
        inj_lat_stats = self.mc.assess_latency_by_obs(planned_routes_injected, executed_routes_injected, rt_exec_dv_getter=dc_dr_dv_getter ,verbose = True)


        sim_plot_params = self.params['const_sim_inst_params']['sim_plot_params']
        time_units = sim_plot_params['obs_aoi_plot']['x_axis_time_units']
        print('------------------------------')
        print('Average AoI by obs, at collection time')
        obs_aoi_stats_at_collection = self.mc.assess_aoi_by_obs_target(planned_routes, executed_routes_regular,include_routing=False,rt_poss_dv_getter=rt_cont_plan_dv_getter, rt_exec_dv_getter=dc_dr_dv_getter ,aoi_x_axis_units=time_units,verbose = True)

        print('------------------------------')
        print('Average AoI by obs, with routing')
        obs_aoi_stats_w_routing = self.mc.assess_aoi_by_obs_target(planned_routes, executed_routes_regular,include_routing=True,rt_poss_dv_getter=rt_cont_plan_dv_getter, rt_exec_dv_getter=dc_dr_dv_getter ,aoi_x_axis_units=time_units,verbose = True)



        time_units = sim_plot_params['sat_cmd_aoi_plot']['x_axis_time_units']
        print('------------------------------')

        #  this is indexed by sat index
        sats_cmd_update_hist = met_util.get_all_sats_cmd_update_hist_removed(self.sat_id_order,self.postRunData)
        aoi_sat_cmd_stats = self.mc.assess_aoi_sat_ttc_option(sats_cmd_update_hist,ttc_option='cmd',input_time_type='datetime',aoi_x_axis_units=time_units,verbose = True)

        #  this is  indexed by ground station index
        time_units = sim_plot_params['sat_tlm_aoi_plot']['x_axis_time_units']

        print('------------------------------')
        sats_tlm_update_hist = met_util.get_all_sats_tlm_update_hist_removed(self.sat_id_order,gs_in_indx_order,self.gs_id_ignore_list,self.postRunData)
        aoi_sat_tlm_stats = self.mc.assess_aoi_sat_ttc_option(sats_tlm_update_hist,ttc_option='tlm',input_time_type='datetime',aoi_x_axis_units=time_units,verbose = True)


        print('------------------------------')
        e_rsrc_stats = self.mc.assess_energy_resource_margin(energy_usage,verbose = True)
        d_rsrc_stats = self.mc.assess_data_resource_margin(data_usage,verbose = True)

        calc_window_utilization = True
        if calc_window_utilization:
            all_link_acts = [dlnk for dlnks in dlnk_winds_flat for dlnk in dlnks]
            all_link_acts += [xlnk for xlnks in xlnk_winds_flat for xlnk in xlnks]

            executed_acts = copy([dlnk for dlnks in dlnks_exe for dlnk in dlnks])
            executed_acts += copy([xlnk for xlnks in xlnks_exe for xlnk in xlnks])

            def all_acts_dv_getter(act):
                return act.original_data_vol
            def exec_acts_dv_getter(act):
                return act.executed_data_vol

            link_stats = self.mc.assess_link_utilization(all_link_acts, executed_acts, all_acts_dv_getter,exec_acts_dv_getter,verbose=True)


        output_path = self.params['output_path']
        if not os.path.exists(output_path+'pickles'):       # /outputs/pickles
            if not os.path.exists(output_path):             # /outputs
                os.mkdir(output_path)
            os.mkdir(output_path+'pickles')

        # saving cus it broke, json so we can read it
        with open(output_path+'pickles/pre-stat.json','w') as f:
            json.dump( {
                "average_obvs_throughput":dv_stats["average_obvs_throughput"],
                "rg_ave_obs_dv_exec":dv_stats["ave_obs_dv_exec"],
                "rg_ave_obs_dv_poss":dv_stats["ave_obs_dv_poss"],
                "inj_ave_obs_dv_exec":inj_dv_stats["ave_obs_dv_exec"],
                "inj_ave_obs_dv_poss":inj_dv_stats["ave_obs_dv_poss"],
                "rg_median_obs_initial_lat_exec":lat_stats["median_obs_initial_lat_exec"],
                "inj_median_obs_initial_lat_exec":inj_lat_stats["median_obs_initial_lat_exec"],
                "median_av_aoi_exec":obs_aoi_stats_w_routing["median_av_aoi_exec"],
                "median_ave_e_margin_prcnt":e_rsrc_stats["median_ave_e_margin_prcnt"],
                "median_ave_d_margin_prcnt":d_rsrc_stats["median_ave_d_margin_prcnt"]
                },
                f, indent=4, separators=(',', ': '))

        # but like this so we can reload it perfectly
        with open(output_path+'pickles/pre-stat.pkl','wb') as f:
            pickle.dump( {
                "average_obvs_throughput":dv_stats["average_obvs_throughput"],
                "rg_ave_obs_dv_exec":dv_stats["ave_obs_dv_exec"],
                "rg_ave_obs_dv_poss":dv_stats["ave_obs_dv_poss"],
                "inj_ave_obs_dv_exec":inj_dv_stats["ave_obs_dv_exec"],
                "inj_ave_obs_dv_poss":inj_dv_stats["ave_obs_dv_poss"],
                "rg_median_obs_initial_lat_exec":lat_stats["median_obs_initial_lat_exec"],
                "inj_median_obs_initial_lat_exec":inj_lat_stats["median_obs_initial_lat_exec"],
                "median_av_aoi_exec":obs_aoi_stats_w_routing["median_av_aoi_exec"],
                "median_ave_e_margin_prcnt":e_rsrc_stats["median_ave_e_margin_prcnt"],
                "median_ave_d_margin_prcnt":d_rsrc_stats["median_ave_d_margin_prcnt"]
                },f)

        # GET AND PRINT ACTIVITY FAILURE STATS
        # 1) get all failure dictionaries and count up failure of each type
        firstSatID = self.sat_id_order[0]
        exec_failure_types = self.postRunData[firstSatID]['failures_exec'].keys()
        non_exec_failure_types = self.postRunData[firstSatID]['failures_nonexec'].keys()

        total_exec_failures_dict = {}
        total_non_exec_failures_dict = {}

        for key in exec_failure_types:
            total_exec_failures_dict[key] = set()

        for sat_id in self.sat_id_order:
            for key in self.postRunData[sat_id]['failures_exec'].keys():
                total_exec_failures_dict[key] |= self.postRunData[sat_id]['failures_exec'][key]

        for key in non_exec_failure_types:
            total_non_exec_failures_dict[key] = set()

        for sat_id in self.sat_id_order:
            for key in self.postRunData[sat_id]['failures_nonexec'].keys():
                total_non_exec_failures_dict[key] |= self.postRunData[sat_id]['failures_nonexec'][key]
                
        # 2) print out each key with the num failures next to it:
        test_metrics_dump = {'Num_Failures_by_Type': {
                'exec': {},
                'non-exec': {}
            }
        }
        print('========Totals for Activity Failures by Type===========')
        total_exec_failures_by_act = {
            'xlnk': set(),
            'dlnk': set(),
            'obs': set()
        }
        # print out and save EXEC failures
        for failure_type in total_exec_failures_dict.keys():
            num_failures = len(total_exec_failures_dict[failure_type])
            xlnk_fails = [act for act in total_exec_failures_dict[failure_type] if isinstance(act,XlnkWindow)]
            dlnk_fails = [act for act in total_exec_failures_dict[failure_type] if isinstance(act,DlnkWindow)]
            obs_fails = [act for act in total_exec_failures_dict[failure_type] if isinstance(act,ObsWindow)]
            if num_failures > 0:
                print('"%s": Total: %d, Obs: %d, Xlnk: %d, Dlnk: %d' %(failure_type,num_failures,
                                                                       len(obs_fails),len(xlnk_fails),len(dlnk_fails)))

            print(failure_type)
            print("xlnk:", xlnk_fails)
            print("dlnk:",dlnk_fails)
            print("obs:",obs_fails)
            print("=========================")

            test_metrics_dump['Num_Failures_by_Type']['exec'][failure_type] =  {
                'xlnk': len(xlnk_fails),
                'dlnk': len(dlnk_fails),
                'obs': len(obs_fails)
            }

            for act_type in total_exec_failures_by_act.keys():
                # an xlnk or downlink can fail for multiple reasons, so need to get unique total set of each type
                if act_type == 'xlnk':
                    for xlnk in xlnk_fails:
                        total_exec_failures_by_act[act_type].add(xlnk)
                elif act_type == 'dlnk':
                    for dlnk in dlnk_fails:
                        total_exec_failures_by_act[act_type].add(dlnk)
                else:
                    for obs in obs_fails:
                        total_exec_failures_by_act[act_type].add(obs)

        print("NON EXEC FAILURES")
        # print out and save NON-EXEC failures:
        for failure_type in total_non_exec_failures_dict.keys():
            num_failures = len(total_non_exec_failures_dict[failure_type])
            xlnk_fails = [act for act in total_non_exec_failures_dict[failure_type] if isinstance(act,XlnkWindow)]
            dlnk_fails = [act for act in total_non_exec_failures_dict[failure_type] if isinstance(act,DlnkWindow)]
            obs_fails = [act for act in total_non_exec_failures_dict[failure_type] if isinstance(act,ObsWindow)]
            if num_failures > 0:
                print('"%s": Total: %d, Obs: %d, Xlnk: %d, Dlnk: %d' %(failure_type,num_failures,
                                                                       len(obs_fails),len(xlnk_fails),len(dlnk_fails)))

            print(failure_type)
            print("xlnk:",xlnk_fails)
            print("dlnk:",dlnk_fails)
            print("obs:",obs_fails)
            print("=========================")

            test_metrics_dump['Num_Failures_by_Type']['non-exec'][failure_type] =  {
                'xlnk': len(xlnk_fails),
                'dlnk': len(dlnk_fails),
                'obs': len(obs_fails)
            }


        test_metrics_dump['Percentage_of_Exec_Act_Failure_by_Act'] = {}
        print('======Total activity failure percentages=====')
        executed_link_acts = set(executed_acts) # makes a set of all executed xlnks and dlnks to avoid double counting
        executed_acts_dict = {
            'xlnk': set(act for act in executed_link_acts if isinstance(act,XlnkWindow)),
            'dlnk': set(act for act in executed_link_acts if isinstance(act,DlnkWindow)),
            'obs': set(obs for obs_winds_by_sat in obs_winds for obs in obs_winds_by_sat)
        }
        for act_type in total_exec_failures_by_act.keys():
            try:
                percent_failed = 100*len(total_exec_failures_by_act[act_type])/len(executed_acts_dict[act_type])
            except ZeroDivisionError:
                percent_failed = 0
            print('%s: %.2f %%' % (act_type,percent_failed))
            test_metrics_dump['Percentage_of_Exec_Act_Failure_by_Act'][act_type] = percent_failed

            
        print('=============Total Possible and Executed DV=============')
        print('Regular Possible Routed DV: %.2f Mb' % dv_stats['total_poss_dv'])
        print('Regular Executed DV: %.2f Mb' % dv_stats['total_exec_dv'])
        print('Percentage Regular Executed / Poss DV: %.2f %%' % (dv_stats['total_exec_dv']/dv_stats['total_poss_dv'] * 100 if dv_stats['total_poss_dv'] > 0 else 0))
        
        if inj_dv_stats['total_poss_dv']:
            print('Injected Possible Routed DV: %.2f Mb' % inj_dv_stats['total_poss_dv'])
            print('Injected Executed DV: %.2f Mb' % inj_dv_stats['total_exec_dv'])
            print('Percentage Injected Executed / Poss DV: %.2f %%' % (inj_dv_stats['total_exec_dv']/inj_dv_stats['total_poss_dv'] * 100 if inj_dv_stats['total_poss_dv'] > 0 else 0 ))

            print('Total Possible Routed DV: %.2f Mb' % (dv_stats['total_poss_dv']+inj_dv_stats['total_poss_dv']))
            print('Total Executed DV: %.2f Mb' % (dv_stats['total_exec_dv']+inj_dv_stats['total_exec_dv']))
            print('Percentage Total Executed / Poss DV: %.2f %%' % ((dv_stats['total_exec_dv']+inj_dv_stats['total_exec_dv'])/(inj_dv_stats['total_poss_dv'] +dv_stats['total_poss_dv'] )* 100))
        else:
            print('No injected obs dv possible')

        # FOR MULTI-RUN TEST STATS - DON'T DELETE  BELOW
        # set run name based on settings:
        SRP_setting = self.params['const_sim_inst_params']['lp_general_params']['use_self_replanner']

        test_metrics_dump['dv_stats'] = deepcopy(dv_stats) # copy this since we are deleting keys
        del test_metrics_dump['dv_stats']['poss_dvs_by_obs'] # remove poss_dvs_by_obs from dv_stats (can't write to json)
        test_metrics_dump['dv_stats']['exec_over_poss'] = dv_stats['total_exec_dv']/dv_stats['total_poss_dv']
        test_metrics_dump['d_rsrc_stats'] = d_rsrc_stats # for data margin
        test_metrics_dump['e_rsrc_stats'] = e_rsrc_stats # for energy margin

        test_metrics_dump['lat_stats'] = deepcopy(lat_stats) # copy this since we are deleting keys
        # delete things that can't be written to json
        del test_metrics_dump['lat_stats']['executed_final_lat_by_obs_exec']
        del test_metrics_dump['lat_stats']['executed_initial_lat_by_obs_exec']
        del test_metrics_dump['lat_stats']['possible_initial_lat_by_obs_exec']

        test_metrics_dump['obs_aoi_stats_w_routing'] = obs_aoi_stats_w_routing
        test_metrics_dump['obs_aoi_stats_at_collection'] = obs_aoi_stats_at_collection

        GS_disrupted_list = list(self.params['const_sim_inst_params']['sim_run_perturbations']['schedule_disruptions'].keys())
        if GS_disrupted_list:
                GS_disrupted = GS_disrupted_list[0] # assumes only 1 GS disrupted at a time
        else:
                GS_disrupted = None
        tx_status = self.params['sim_case_config']['use_crosslinks']
        try:
            name = 'multi_%s_SRP_and_%s_tx_status' % (SRP_setting,tx_status)
            multirun_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../', 'multirun_tests/'))
            fln = multirun_path + "/" + name + ".json"
            with open(fln,'w') as f:
                json.dump(test_metrics_dump,f, indent=4, separators=(',', ': ')) 
            print("json created: " + name)
        except KeyError:
            pass
        
        print('SRP SETTING IS: %s, GS DISRUPTED IS: %s' % (SRP_setting, GS_disrupted))

        # PRINT FINAL STATS
        print("Global Planner performance under simulation:")
        print("| - | Obs. Throughput |     OT      | Med. Obs Latency |    MOLe     | Med. Obs Target | Med. Sat-ave  | Med. Sat-ave |")
        print("| - |    (ave % Max)  | w/ Inj (LP) |    (executed)    | w/ Inj (LP) |   data ave AOI  | Energy Margin | Data Margin  |")
        print("| - |    {:7.2f}      |   {:7.2f}   |     {}      |   {}   |    {}      |   {}     |   {}    |"
            .format   (
                dv_stats["average_obvs_throughput"],
                inj_dv_stats["average_obvs_throughput"],
                ( '   -   ' if not lat_stats["median_obs_initial_lat_exec"] else "{:7.2f}".format(lat_stats["median_obs_initial_lat_exec"]) ),  # TODO - reform this stat similarly
                ( '   -   ' if not inj_lat_stats["median_obs_initial_lat_exec"] else "{:7.2f}".format(inj_lat_stats["median_obs_initial_lat_exec"]) ),
                ( '   -   ' if not obs_aoi_stats_w_routing["median_av_aoi_exec"] else "{:7.2f}".format(obs_aoi_stats_w_routing["median_av_aoi_exec"]) ),
                ( '   -   ' if not e_rsrc_stats["median_ave_e_margin_prcnt"] else "{:7.2f}".format(e_rsrc_stats["median_ave_e_margin_prcnt"]) ),
                ( '   -   ' if not d_rsrc_stats["median_ave_d_margin_prcnt"] else "{:7.2f}".format(d_rsrc_stats["median_ave_d_margin_prcnt"]) )
                )
            )

        
        ######
        # metrics plots
        output_path = self.params['output_path']
        if not os.path.exists(output_path+'plots'):         # /outputs/plots
            if not os.path.exists(output_path):             # /outputs
                os.mkdir(output_path)
            os.mkdir(output_path+'plots')
            
        print('Creating and saving plots to: %s' % output_path + 'plots')

        self.sim_plotter.plot_obs_aoi_at_collection(
            # self.obs_target_id_order,
            obs_aoi_stats_at_collection['exec_targIDs_found'] ,
            obs_aoi_stats_at_collection['aoi_curves_by_targID_exec']
        )

        self.sim_plotter.plot_obs_aoi_w_routing(
            # self.obs_target_id_order,
            obs_aoi_stats_w_routing['exec_targIDs_found'] ,
            obs_aoi_stats_w_routing['aoi_curves_by_targID_exec']
        )

        curves_by_indx = aoi_sat_cmd_stats['aoi_curves_by_sat_indx']
        cmd_aoi_curves_by_sat_id = {self.sat_id_order[sat_indx]:curves for sat_indx,curves in curves_by_indx.items()}

        self.sim_plotter.plot_sat_cmd_aoi(
            self.sat_id_order,
            cmd_aoi_curves_by_sat_id,
            all_downlink_winds = self.gs_network.scheduler.all_windows_dict['dlnk_winds_flat'],
            gp_replan_freq = self.const_sim_inst_params['sim_gs_network_params']['gsn_ps_params']['replan_interval_s']
        )

        if non_exec_failures_dicts_list:
            # also want to plot activity failures vs. GP plan age (cmd AoI) (non-exec failures)
            # NOTE: the aoi_curves_by_sad_id is inside "run_and_plot_metrics" so can't call it here
            self.sim_plotter.sim_plot_all_sats_failures_on_cmd_aoi(
                self.sat_id_order,
                non_exec_failures_dicts_list,
                cmd_aoi_curves_by_sat_id
            )

        curves_by_indx = aoi_sat_tlm_stats['aoi_curves_by_sat_indx']
        tlm_aoi_curves_by_sat_id = {self.sat_id_order[sat_indx]:curves for sat_indx,curves in curves_by_indx.items()}
        self.sim_plotter.plot_sat_tlm_aoi(
            self.sat_id_order,
            tlm_aoi_curves_by_sat_id
        )


        # plot obs latency histogram, planned routes
        
        pltl.plot_histogram(
            data=obs_aoi_stats_w_routing['av_aoi_by_targID_exec'].values(),
            num_bins = 40,
            plot_type = 'histogram',
            x_title='AoI (hours)',
            y_title='Number of Obs Targets',
            # plot_title = 'CIRCINUS Sim: Average AoI Histogram, with routing (dv req %.1f Mb)'%(mc.min_obs_dv_dlnk_req),
            plot_title = 'CIRCINUS Sim: Average AoI Histogram, with routing',
            plot_size_inches = (12,5.5),
            show=False,
            fig_name=output_path+'plots/csim_obs_aoi_routing_executed_hist.pdf'
        )
        
        # plot obs latency histogram, planned routes
        pltl.plot_histogram(
            data=obs_aoi_stats_at_collection['av_aoi_by_targID_exec'].values(),
            num_bins = 40,
            plot_type = 'histogram',
            x_title='AoI (hours)',
            y_title='Number of Obs Targets',
            # plot_title = 'CIRCINUS Sim: Average AoI Histogram, at collection (dv req %.1f Mb)'%(mc.min_obs_dv_dlnk_req),
            plot_title = 'CIRCINUS Sim: Average AoI Histogram, at collection',
            plot_size_inches = (12,5.5),
            show=False,
            fig_name=output_path+'plots/csim_obs_aoi_collection_executed_hist.pdf'
        )

        # for SSO
        # lat_hist_x_range = (0,250) # minutes
        # lat_hist_num_bins = 50
        # for walker
        lat_hist_x_range = (0,150) # minutes
        lat_hist_y_range = (0,200) # minutes
        # lat_hist_num_bins = 270
        lat_hist_num_bins = 500

        
        # plot obs latency histogram, planned routes
        pltl.plot_histogram(
            data=lat_stats['possible_initial_lat_by_obs_exec'].values(),
            num_bins = lat_hist_num_bins,
            plot_type = 'histogram',
            plot_x_range = lat_hist_x_range,
            plot_y_range = lat_hist_y_range,
            x_title='Latency (mins)',
            y_title='Number of Obs Windows',
            # plot_title = 'CIRCINUS Sim: Initial Latency Histogram, planned (dv req %.1f Mb)'%(mc.min_obs_dv_dlnk_req),
            plot_title = 'CIRCINUS Sim: Initial Latency Histogram, planned',
            plot_size_inches = (12,3.5),
            show=False,
            fig_name=output_path+'plots/csim_obs_lat_planned_hist.pdf'
        )

        
        # plot obs latency histogram, executed routes
        pltl.plot_histogram(
            data=lat_stats['executed_initial_lat_by_obs_exec'].values(),
            num_bins = lat_hist_num_bins,
            plot_type = 'histogram',
            plot_x_range = lat_hist_x_range,
            plot_y_range = lat_hist_y_range,
            x_title='Latency (mins)',
            y_title='Number of Obs Windows',
            # plot_title = 'CIRCINUS Sim: Initial Latency Histogram, executed (dv req %.1f Mb)'%(mc.min_obs_dv_dlnk_req),
            plot_title = '',
            plot_size_inches = (12,3.5),
            show=False,
            fig_name=output_path+'plots/csim_obs_lat_executed_hist.pdf'
        )

        with open(output_path+'plots/exec_obs_lat_reg_cdf_data.json','w') as f:
            json.dump(list(lat_stats['executed_initial_lat_by_obs_exec'].values()), f, indent=4, separators=(',', ': '))

        
        # plot obs latency histogram, executed routes
        pltl.plot_histogram(
            data=lat_stats['executed_initial_lat_by_obs_exec'].values(),
            num_bins = lat_hist_num_bins,
            plot_type = 'cdf',
            plot_x_range = lat_hist_x_range,
            plot_y_range = lat_hist_y_range,
            x_title='Latency (mins)',
            y_title='Fraction of Obs Windows',
            # plot_title = 'CIRCINUS Sim: Initial Latency Histogram, executed (dv req %.1f Mb)'%(mc.min_obs_dv_dlnk_req),
            plot_title = 'CIRCINUS Sim: Initial Latency CDF, executed regular',
            plot_size_inches = (12,3.5),
            show=False,
            fig_name=output_path+'plots/csim_obs_lat_executed_cdf.pdf'
        )


        ############
        # injected routes latency plots

        # plot obs latency histogram, executed routes
        pltl.plot_histogram(
            data=inj_lat_stats['executed_initial_lat_by_obs_exec'].values(),
            num_bins = lat_hist_num_bins,
            plot_type = 'histogram',
            plot_x_range = lat_hist_x_range,
            plot_y_range = lat_hist_y_range,
            x_title='Latency (mins)',
            y_title='Number of Obs Windows',
            # plot_title = 'CIRCINUS Sim: Initial Latency Histogram, executed (dv req %.1f Mb)'%(mc.min_obs_dv_dlnk_req),
            plot_title = 'CIRCINUS Sim: Initial Latency Histogram, executed injected',
            plot_size_inches = (12,3.5),
            show=False,
            fig_name=output_path+'plots/csim_obs_lat_injected_hist.pdf'
        )

        with open(output_path+'plots/exec_obs_lat_inj_cdf_data.json','w') as f:
            json.dump(list(inj_lat_stats['executed_initial_lat_by_obs_exec'].values()), f, indent=4, separators=(',', ': '))

        # plot obs latency histogram, executed routes
        pltl.plot_histogram(
            data=inj_lat_stats['executed_initial_lat_by_obs_exec'].values(),
            num_bins = lat_hist_num_bins,
            plot_type = 'cdf',
            plot_x_range = lat_hist_x_range,
            plot_y_range = lat_hist_y_range,
            x_title='Latency (mins)',
            y_title='Fraction of Obs Windows',
            # plot_title = 'CIRCINUS Sim: Initial Latency Histogram, executed (dv req %.1f Mb)'%(mc.min_obs_dv_dlnk_req),
            plot_title = 'CIRCINUS Sim: Initial Latency CDF, executed injected',
            plot_size_inches = (13,3.5),
            show=False,
            fig_name=output_path+'plots/csim_obs_lat_injected_cdf.pdf'
        )

    def get_metrics_params(self):
        metrics_params = {}

        scenario_params = self.params['orbit_prop_params']['scenario_params']
        sat_params = self.params['orbit_prop_params']['sat_params']
        obs_params = self.params['orbit_prop_params']['obs_params']
        sim_metrics_params = self.params['const_sim_inst_params']['sim_metrics_params']
        sim_plot_params = self.params['const_sim_inst_params']['sim_plot_params']
        as_params = self.params['gp_general_params']['activity_scheduling_params']

        # these are used for AoI calculation
        metrics_params['met_obs_start_dt']  = self.params['const_sim_inst_params']['sim_run_params']['start_utc_dt']
        metrics_params['met_obs_end_dt']  = self.params['const_sim_inst_params']['sim_run_params']['end_utc_dt']

        metrics_params['num_sats']=sat_params['num_sats']
        metrics_params['num_targ'] = obs_params['num_targets']
        metrics_params['all_targ_IDs'] = [targ['id'] for targ in obs_params['targets']]
        metrics_params['min_obs_dv_dlnk_req'] = as_params['min_obs_dv_dlnk_req_Mb']

        metrics_params['latency_calculation_params'] = sim_metrics_params['latency_calculation']
        metrics_params['targ_id_ignore_list'] = sim_metrics_params['targ_id_ignore_list']
        metrics_params['aoi_units'] = sim_metrics_params['aoi_units']

        metrics_params['sats_emin_Wh'] = []
        metrics_params['sats_emax_Wh'] = []
        for p_params in sat_params['power_params_by_sat_id'].values():
            sat_edot_by_mode,sat_batt_storage,power_units,charge_eff,discharge_eff = \
                io_tools.parse_power_consumption_params(p_params)

            metrics_params['sats_emin_Wh'].append(sat_batt_storage['e_min'])
            metrics_params['sats_emax_Wh'].append(sat_batt_storage['e_max'])

        metrics_params['sats_dmin_Gb'] = []
        metrics_params['sats_dmax_Gb'] = []
        for d_params in sat_params['data_storage_params_by_sat_id'].values():
            d_min = d_params['d_min']
            d_max = d_params['d_max']

            metrics_params['sats_dmin_Gb'].append(d_min)
            metrics_params['sats_dmax_Gb'].append(d_max)

        metrics_params['timestep_s'] = scenario_params['timestep_s']

        return metrics_params

