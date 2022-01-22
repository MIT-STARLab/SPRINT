from datetime import timedelta
import socket
from circinus_tools.scheduling.io_processing import SchedIOProcessor
from circinus_tools  import time_tools as tt
from circinus_tools.metrics.metrics_calcs import MetricsCalcs
from circinus_tools  import io_tools
from circinus_tools.activity_bespoke_handling import ActivityTimingHelper
from circinus_sim.constellation_sim_tools.sim_agents import SimSatellite
from circinus_sim.constellation_sim_tools.lp_wrapper import LocalPlannerWrapper
from circinus_sim.constellation_sim_tools.Transmission_Simulator import Transmission_Simulator
from sprint_tools.Constellation_STN import Constellation_STN
from Removed_Satellite.Removed_Satellite_Server import RemovedSatelliteServer
from Removed_Satellite.Removed_Satellite_Client import RemovedSatelliteClient
from Removed_Satellite.BlockingDict import BlockingDict
from sprint_tools.Sprint_Types import AgentType
from threading import Thread,  Condition
import pyutilib

import time 
from Removed_Satellite.Message_ID_Assigner import MessageIDAssigner
import multiprocessing as mp

pyutilib.subprocess.GlobalData.DEFINE_SIGNAL_HANDLERS_DEFAULT = False

class RemovedSatellite:
    """
    Class that simulates a satellite on a separate device, acting as a wrapper class to the original
    "satellite" class in sim_agents
    
    Communicates with satellites and ground simulation (on separate devices) using server/client protocol

    """

    GROUND_SERVER_PORT = 54201
    VERBOSE = True

    def __init__(self, general_config:dict):
        """
        initializes removed satellite
        """
        self.general_config = general_config
        self.params = None
        self.sat_params,self.orbit_params = None, None
        self.sim_run_params = None
        self.sim_start_dt, self.sim_end_dt = None,None

        self.satellite = None              # The "original" satellite object
        self.sim_lock = Condition()        # Lock on sim. Only used for sim-related messages
        self.gs_id_order = None            # List of gs ids, ordered by their gs index
        self.sat_id_order = None           # List of sat ids, ordered by sat index
        self.num_sats = -1                 # The number of satellites in the simulation. -1 is invalid.
        self.sat_index = -1                # Satellite index. -1 is invalid.
        self.dt = -1
        self.io_proc = None

        ##### Server/Client Params ######
        self.active = False
        self.got_params = False
        self.got_ips = False
        self.got_injected_obs = False
        self.got_updated_windows = False
        self.msgsToSend = {}                                                     # Queue of messages to pass to client
        self.conn_to_server,self.server_conn = self.get_pipe_connections()       # Server that "listens" for
                                                                                 # incoming messages
        self.responses = BlockingDict()
        self.server_port = None
        self.server_proc = None

        self.client = self.set_up_client()                                       # Client that sends messages
                                                                                 # given target
        self.sat_id = None
        self.ecl_winds = None

        ## Message params ###
        self.idsToMsgType = {}
        self.msgTypeToIDs = {"STATES":set(),"PLAN":set(),"BDT":set(),
                             "PLAN_LP":set(),"PLAN_PROP":set(),
                             "SAT_STATS":set()}

        self.idsToTargets = {}
        self.msgIDAssigner = MessageIDAssigner()


        ## Flag to start and end the sim
        self.START_REQ = False
        self.POST_RUN_REQ = False
        self.END_SIM = False

        # Initialize and start controller
        t = Thread(target = self.run_controller)
        t.setDaemon(True)
        t.start()

        # Join simulation
        self.join_sim()


        with self.sim_lock:
            self.sim_lock.wait_for(lambda: self.got_params)

            self.numPeers = self.num_sats
            self.numFinishedActs = 0            # Number of peers that finished sending messages in executive acts
            self.numFinishedProps = 0           # Number of peers finished propagating their plans
            self.numReadyForNextTimeStep = 0    # Number of peers ready for next time step

            # metrics calculation
            self.mc = MetricsCalcs(self.get_metrics_params())

            # Also create local planner wrapper. it will store inputs that are common across all satellites. T
            # he instance parameters passed to it should be satellite-specific
            self.lp_wrapper = LocalPlannerWrapper(self.params,self.mc)

            self.schedule_disruptions = self.params['sim_case_config']['sim_run_perturbations']['schedule_disruptions']

            #####  End Sim State Truth   #####

            self.Transmission_Simulator = Transmission_Simulator(False,False, self, removed_sat = True)

        with self.sim_lock:
            self.sim_lock.wait_for(lambda: self.active)

        with self.sim_lock:
            self.sim_lock.wait_for(lambda: self.START_REQ)
        self.run()

        with self.sim_lock:
            self.sim_lock.wait_for(lambda:self.END_SIM)
    
    def get_pipe_connections(self):
        """
        Creates pipe connection between Removed Satellite and its server.
        This connection spans multiple processes.
        """
        parent,child = mp.Pipe()
        return parent,child

    @staticmethod
    def run_server(conn:mp.connection.Connection):
        """
        Creates and runs a server
        :param conn: The pipe connection
        """
        p = mp.Process(target = RemovedSatelliteServer,args=(conn,),daemon=True)
        p.start()
        return p

    def set_up_client(self):
        """
        Creates client with no knowledge of other server addresses besides ground server port and address
        """
        groundAddress = self.general_config['rem_gp_server_address']
        return RemovedSatelliteClient(groundAddress,self.GROUND_SERVER_PORT,self.msgsToSend)
    
    def set_up_act_timing(self):
        
        self.act_timing_helper = ActivityTimingHelper(self.sat_params['activity_params'],self.orbit_params['sat_ids_by_orbit_name'],self.sat_params['sat_id_order'],None)

    def set_up_stn(self):
        ##### Simulation State Truth #####
        stn_params = {
            'element_id_by_index': {
                'sat_id_by_indx'    : self.sat_id_order,
                'gs_id_by_indx'     : self.gs_id_order,
                'trget_id_by_indx'  : self.params['orbit_prop_params']['obs_params']['obs_target_id_order']
            },
            'accesses_data' : self.params['orbit_prop_params']['orbit_prop_data']['accesses_data']
        }
        self.access_truth_stn = Constellation_STN(stn_params)

    def set_up_params(self,payload:dict):
        """
        Initializes params, satellite, etc. based on payload
        :param payload: Input params
        """
        self.params = payload["sim_params"]
        self.sat_params = self.params['orbit_prop_params']['sat_params']
        self.orbit_params = self.params['orbit_prop_params']['orbit_params']
        self.sim_run_params = self.params['const_sim_inst_params']['sim_run_params']

        # ================== Setting up Satellite Parameters  =====================
        self.sim_start_dt, self.sim_end_dt = payload["sim_start_dt"], payload["sim_end_dt"]
        id_sim_params = payload["sat_id_sim_satellite_params"]
        id_scenario_params = payload["sat_id_scenario_params"]

        self.sat_id = payload["sat_id"]
        self.msgIDAssigner.setAgentID(self.sat_id)
        self.client.set_id(self.sat_id)
        self.sat_index = payload["sat_index"]

        # ------------------- Get ID order of satellites and gs --------------------
        self.gs_id_order = self.params['orbit_prop_params']['gs_params']['gs_id_order']
        self.sat_id_order = self.params['orbit_prop_params']['sat_params']['sat_id_order']
        self.gs_id_ignore_list = self.params['gp_general_params']['other_params']['gs_id_ignore_list']

        self.num_sats = self.params['orbit_prop_params']['sat_params']['num_sats']
        self.dt = timedelta(seconds=self.sim_run_params['sim_tick_s'])

        # ================== Set up Satellite Dependencies ==================
        self.set_up_act_timing()
        self.set_up_stn()
        self.io_proc = SchedIOProcessor(self.params)

        # ================== Set up Plan DB  Dependencies ==================
        window_uid = -9999
        # ecl_winds is an array with index for each sat_indx
        ecl_winds, window_uid = self.io_proc.import_eclipse_winds(window_uid)
        if window_uid >= 0: raise RuntimeWarning('Saw positive window ID for ecl window hack')

        ecl_winds_by_sat_id = {self.sat_id_order[sat_indx]: ecl_winds[sat_indx] for sat_indx in range(self.num_sats)}
        self.ecl_winds = ecl_winds

        gsn_id = 'gsn'

        plan_db_inputs = {
            "sat_id_order": self.sat_id_order,
            "gs_id_order": self.gs_id_order,
            "other_agent_ids": [gsn_id],
            "initial_state_by_sat_id": self.sat_params['initial_state_by_sat_id'],
            "ecl_winds_by_sat_id": ecl_winds_by_sat_id,
            "power_params_by_sat_id": self.sat_params['power_params_by_sat_id'],
            "resource_delta_t_s": self.sim_run_params['sim_tick_s']
        }

        # ======================== Create Satellite ==========================
        self.satellite = SimSatellite(
            self.sat_id,
            self.sat_index,
            self.sim_start_dt,
            self.sim_end_dt,
            id_scenario_params,
            id_sim_params,
            self.act_timing_helper,
            self,
            self.access_truth_stn,
            removed=True)

        self.satellite.get_plan_db().initialize(plan_db_inputs)

        self.got_params = True
        self.sim_lock.notifyAll()

    def join_sim(self):
        """
        Joins simulation by connecting to Ground server and starting up server
        """

        # Start up server
        p = RemovedSatellite.run_server(self.server_conn)
        self.server_proc = p

        # Wait until server has finished setting up listening socket
        with self.sim_lock:
            self.sim_lock.wait_for(lambda: self.server_port!=None)


        # Connect client to ground server
        self.client.start_ground_connection()

        joinMessage = {'req_type': 'JOIN',
                       'payload': {'address':socket.gethostbyname(socket.gethostname()),
                                   'port': self.server_port},
                       'waitForReply':True
                      }

        self.send_message(joinMessage,"ground")

                
    def run_controller(self):
        """
        Automatically handles message processing whenever it is passed a message

        """
        while True:
            newMsg = self.conn_to_server.recv()
            if type(newMsg) == dict:
                # Data or sim message
                self.handle_message(newMsg)

            elif 'ACK' == newMsg[0]:
                # Check if message is response
                self.handleResponse(newMsg)

            elif 'SERVER_PORT' == newMsg[0]:
                with self.sim_lock:
                    self.server_port = newMsg[1]
                    self.sim_lock.notify_all()

            elif 'ERROR' in newMsg[0]:
                # Error--raise it
                print(newMsg[1])


    def run(self):
        """
        Runs removed satellite simulation
        """
        numLP = 0
        
        self.current_time = self.sim_start_dt
        
        print("{}\n------- Starting Simulation ------\n".format(time.time()))

        while self.current_time < self.sim_end_dt:
            # ======================================================================
            # ====================+=== Activity Execution ==========================
            # ======================================================================

            self.satellite.execution_step(self.current_time)

            
            finishedSendingActsMsg = {'req_type': 'ACTS_DONE', 'payload': None,
                                      'sender': self.sat_id,"waitForReply":True}
            
            self.send_message(finishedSendingActsMsg,broadcast = True)

            with self.sim_lock:
                self.sim_lock.wait_for(lambda: self.numFinishedActs == self.numPeers)
                self.numFinishedActs = 0

            # ======================================================================
            # ============================ Update state ============================
            # ======================================================================

            with self.satellite.lock:
                self.satellite.state_update_step(self.current_time, self.lp_wrapper)

            # =====================================================================================
            # ========= Share local satellite STATES info if appropriate using crosslinks =========
            # =====================================================================================

            with self.satellite.last_broadcast_lock:
                secondsSinceLastBroadcast = (self.current_time - self.satellite.last_broadcast).seconds

            if self.satellite.prop_reg and secondsSinceLastBroadcast > self.satellite.prop_cadence:
                self.satellite.get_exec().state_x_prop(tt.datetime2mjd(self.current_time))

            # ===============================================================================
            # ============================ Planning info sharing ============================
            # ===============================================================================

            # Sat shares PLAN message with other sats if appropriate
            # (flag under reference_model_definitions/sat_regs/zhou_original_sat.json
            # ["sat_model_definition"]["sim_satellite_params"]["crosslink_new_plans_only_during_BDT"])
            # if false, then anytime there is a potential crosslink access, plans will propagate.
            # if true, then plans will only propagate over existing scheduled bulk data tranfer (BDT) Xlnk activites
            if not self.params['const_sim_inst_params']['sim_satellite_params']['crosslink_new_plans_only_during_BDT']:
                with self.satellite.lock:
                    self.satellite.plan_prop(self,tt.datetime2mjd(self.current_time))

            # If a sat LP has run, send that info to gs network so it can use in planning with GP
            if self.satellite.lp_has_run():
                numLP += 1
                self.satellite.push_down_L_plan(self,tt.datetime2mjd(self.current_time))

            # Let all know that satellite finished propagating LP plans, if any
            finishedPropMsg = {'req_type': 'FINISHED_PROP','payload': None,'sender':self.sat_id,"waitForReply":True}
            self.send_message(finishedPropMsg,broadcast = True)

            with self.sim_lock:
                # Wait for everyone to finish propagating plans before saying ready for next update
                self.sim_lock.wait_for(lambda: self.numFinishedProps == self.numPeers)

                self.numFinishedProps = 0 # reset
            readyForNextTimeStepMsg = {'req_type': 'READY_FOR_TIME_UPDATE', 'payload': None,
                                           'sender': self.sat_id,"waitForReply":True}
            self.send_message(readyForNextTimeStepMsg, broadcast=True)

            # Wait until time has updated to move on
            with self.sim_lock:
                self.sim_lock.wait_for(lambda: self.numReadyForNextTimeStep == self.numPeers)
                self.satellite.no_more_bdt = False
                self.current_time += self.dt
                self.numReadyForNextTimeStep = 0


            print("\n==============================================================")
            print("============= CURRENT TIME : {} =============".format(self.current_time))
            print("==============================================================\n")

            
        print("Number of times Local Planner ran:",numLP)

        statsMsg = {'req_type': 'SAT_STATS',
                    'payload': {'plan_props_succeded': self.satellite.stats['plan_props_succeded'],
                                'plan_props_attempted': self.satellite.stats['plan_props_attempted']},
                    'dest': 'ground',
                    'sender': self.sat_id,
                    'waitForReply': True}

        self.send_message(statsMsg,target_id = 'ground')

        with self.sim_lock:
            self.sim_lock.wait_for(lambda: self.POST_RUN_REQ)


    def getAllSatIDs(self):
        """
        Gets all satellite ids, ordered by index
        """
        return self.sat_id_order
        
    def getAllGSIDs(self):
        """
        Gets all gs ids, ordered by index
        """
        return self.gs_id_order
    
    def getAgentType(self,id:str):
        """
        Gets the AgentType of the object with id <id>, based on the enum AgentType
        @param id       Input id
        @return         The AgentType enum value
        """
        
        if id in self.gs_id_order: return AgentType.GS
        elif id in self.sat_id_order: return AgentType.SAT
        return AgentType.GSNET
    
    def getReferenceByID(self,id:str):
        """
        Gets the reference to a satellite by id only if the id matches this
        :param id       The input id string
        :return         self.satellite if id matches self.id, else None
        """
        if id == self.sat_id: return self.satellite
        
        return None

    def send_message(self,message:dict,target_id:str = None, broadcast:bool = False):
        """
        Sends message to satellite using pickle serialization
        Must have either sat_id defined or broadcast = True

        :param message:   The dictionary message to send
        :param target_id: The ID of the target
        :param broadcast: True if sending to ALL satellites and ground (not gs specific), False otherwise.
        :return:          True if successful, False if not. If additional data, instead sends the additional data (only
                          applicable for NON broadcast transmissions)
        
        Message sent successfully if entire message sent and an acknowledgement message received, if we are
        waiting for a reply
        """
        assert target_id or broadcast, "sat_id must be defined or broadcast must be true"
        if 'ACK' in message: isACK = True
        else: isACK = False

        ids = set() 

        if target_id:
            message['dest'] = target_id
            if not isACK:
                msgId = self.msgIDAssigner.assign_id()
                ids.add(msgId)
                message['id'] = msgId

            else:
                msgId = message['id']

            if not isACK:
                if message['req_type'] == 'BDT':
                    self.satellite.bdt_ids_to_msg_id[msgId] = message['payload']['window_id']

            if self.gs_id_order:
                if target_id in self.gs_id_order:
                    target_id = 'ground'

            self.msgsToSend[target_id].put(message)

        elif broadcast:
            assert not isACK
            # Broadcasts message cannot be ACKs
            idsToUse = self.msgIDAssigner.assign_ids(self.numPeers)
            ids.update(idsToUse)

            # Place messages on queue to send
            for peer in self.msgsToSend:
                peerMessage = message.copy() 
                peerMessage['dest'] = peer 
                peerMessage['id'] = idsToUse.pop()
                self.msgsToSend[peer].put(peerMessage)



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

                if not isACK:   return self.getResponse(msgId)
        else:
            # Record message type and ID to process responses later
            # Only for non ACK messages
            if not isACK:
                msgType = message['req_type']
                if msgType == 'PLAN':
                    if message['handle_lp']:
                        msgType = 'PLAN_LP'
                    elif message['plan_prop']:
                        msgType = 'PLAN_PROP'


                for _id in ids:
                    # Record which ids were used, and for which message types
                    self.idsToMsgType[_id] = msgType
                    self.idsToTargets[_id] = target_id

                self.msgTypeToIDs[msgType].update(ids)


    def sendResponse(self,msgID:str,target:str,ack:bool,txWaitForReply:bool,response:dict = None):
        """
        Sends response for a message.

        :param msgID:           The ID of the sent message
        :param target:          The ID of the sending agent
        :param ack:             True if acknowledged, false otherwise
        :param txWaitForReply:  True if tx is actively waiting for reply
        :param response:        (If any) additional response data
        """
        response = {"ACK": ack, "payload": response,"id": msgID,"waitForReply":False,'txWaitForReply':txWaitForReply}

        self.send_message(response,target_id=target)

    def getResponse(self, msgID : str):
        """
        Gets the response for a message
        :param msgID:   The message ID
        :return:        The response. If no other data included, then True if acknowledged and False otherwise.
                        Else, the response data
        """

        return self.responses.get(msgID)

    def handleResponse(self,response:tuple):
        """
        Handles delayed received response for PLAN, STATES, AND BDT

        For PLAN:
            - Updates the satellite's states, specifically successful PLAN sends
        For STATES:
            - Checks which applicable satellites have not ACKED (or have ACKED)
            - Updates the last time of satellite broadcast
        For BDT:
            - Updates ACKed BDT statements, essential for SRP

        :param response: The response, structured as: ("ACK",_id, payload or success)

        """

        # Remove message ID from nonACKed IDs
        msgId = response[1]
        waitForReply = response[3]

        if waitForReply:
            self.responses.put(msgId,response[2])
            return

        msgType = self.idsToMsgType.pop(msgId)
        original_target = self.idsToTargets.pop(msgId)
        idsToTrack = self.msgTypeToIDs[msgType]
        idsToTrack.remove(msgId)

        if 'PLAN' in msgType:

            if msgType == 'PLAN_PROP' and len(idsToTrack) == 0:
                # A PLAN message that is part of a propagation
                self.satellite.arbiter.sats_propped_to[original_target].append(self.current_time)
                self.satellite.stats['plan_props_succeded'] += 1

            elif msgType == 'PLAN_LP':
                # A PLAN message that is part of Local Planner (LP) planning propagation
                self.satellite.arbiter.set_external_share_plans_updated(False)

            elif type(response[2]) == dict:
                # Check if there is a payload
                self.satellite.receive_message(response[2])

        elif msgType == 'STATES':
            if len(idsToTrack) == 0: # All applicable satellites have ACKed the state message
                with self.satellite.last_broadcast_lock:
                    self.satellite.last_broacast = self.current_time

        elif msgType == 'BDT':
            import time
            dv_txed, tx_success = response[2]

            _id = self.satellite.bdt_ids_to_msg_id.pop(msgId)

            if not tx_success:
                bdt_ack = (_id,None)
            else:
                bdt_ack = (_id,dv_txed)

            self.satellite.bdt_ids_acked.put(bdt_ack)

    def handle_message(self,message:dict):
        """
        Handles message based on message type, sending response after ingestion
        Assumes message is valid

        If sim is not active, then waits for initialization related messages:
        Messages include:
        - IP addresses of all other satellites/ground servers
        - Injected observations
        - Satellite window initialization
        
        :param message      The incoming message, deserialized
        """
        messageType = message["req_type"]
        key = message['id']
        target = message['sender']
        waitForReply = message['waitForReply']

        if not self.active:  # Check if initialization messages
            """
            # We MUST receive the following before starting the simulation: 
            # - Initialization parameters, aka INIT_PARAMS. Must be received FIRST
            # - IP addresses of all other satellite servers. Denoted as ALL_IPS
            # - Injected observations (even if there are none). Denoted as INJECT_OBS
            # - Windows initialization, denoted as SAT_WINDOWS_INIT
            # Once we receive all of these, we are ACTIVE and can start the simulation
            # whenever the ground simulation sends the START message 
                        
            """

            with self.sim_lock:
                if not self.got_params:
                    if messageType != "INIT_PARAMS":
                        print("WARNING: Unknown message type.")
                        self.sendResponse(key, target,False,waitForReply)
                    self.set_up_params(message["payload"])

                    self.sendResponse(key, target,True,waitForReply)
                    self.got_params = True

                else:
                    if messageType == "ALL_IPS":                # Getting IP addresses
                        self.client.set_gs_ids(self.gs_id_order)
                        self.client.set_ips(message["payload"])
                        self.got_ips = True
                        self.sendResponse(key, target,True,waitForReply)

                    elif messageType == "INJECT_OBS":  # Getting injected observations
                        injected_obs = message["payload"]
                        with self.satellite.lock:
                            self.satellite.inject_obs(injected_obs)
                            self.got_injected_obs = True
                            self.sendResponse(key,target, True,waitForReply)

                    elif messageType == "SAT_WINDOWS_INIT":  # Updating observation windows
                        with self.satellite.lock:
                            self.satellite.get_plan_db().sat_windows_dict = message["payload"].copy()
                            self.got_updated_windows = True
                            self.sendResponse(key, target,True,waitForReply)

                    else:
                        print("WARNING: Unknown message type.")


                self.active = self.got_ips and self.got_injected_obs and self.got_updated_windows
                if self.active: self.sim_lock.notifyAll()
        else:
            if messageType in {"PLAN","BDT","STATES"}:

                with self.satellite.lock:

                    # First, receive the message
                    response = self.satellite.receive_message(message)

                    if messageType == 'PLAN':
                        if message['exchange']:
                            """
                            If it was a PLAN message that requires a PLAN exchange message, 
                            generate PLAN message and add as payload to response 
                            """
                            new_time, dest = message['payload']['new_time'], message['sender']
                            info_option = message['payload']['info_option']
                            if dest in self.sat_id_order:
                                self.satellite.get_plan_db().update_self_ttc_time(new_time)
                            response = self.satellite.make_planning_message(dest,info_option)

                    self.sendResponse(key,target,True,waitForReply,response)

            elif messageType == 'NEXT_WINDOW_UPDATE':
                """
                Update window based on ground update 
                """
                with self.satellite.lock:
                    self.updateNextWindow(message)
                    self.sendResponse(key, target,True,waitForReply)
                    self.satellite.lock.release()

            elif messageType == 'ACTS_DONE':
                """
                Count up the number of peers (ground, satellites) that have finished executing their actions
                for this time step. Once all others are finished executing actions, notify any waiting threads 
                """
                with self.sim_lock:
                    self.numFinishedActs += 1
                    self.sendResponse(key,target,True,waitForReply)
                    if self.numFinishedActs == self.numPeers: self.sim_lock.notifyAll()

            elif messageType == 'READY_FOR_TIME_UPDATE':
                """
                Count up the number of peers (ground,satellites) that are ready for the next time step. 
                Once all others are ready, notify any waiting threads 
                """
                with self.sim_lock:
                    self.numReadyForNextTimeStep += 1
                    self.sendResponse(key, target,True,waitForReply)
                    if self.numReadyForNextTimeStep == self.numPeers: self.sim_lock.notifyAll()

            elif messageType == 'FINISHED_PROP':
                """
                Count up the number of peers (ground,satellites) that have finish propagating information. 
                Once all others are ready, notify any waiting threads 
                """
                with self.sim_lock:
                    self.numFinishedProps += 1
                    self.sendResponse(key, target,True,waitForReply)
                    if self.numFinishedProps == self.numPeers:
                        self.sim_lock.notifyAll()

            elif messageType == "XLINK_FAILURE":
                """
                Record if a neighboring satellite experienced a crosslink failure with this satellite. 
                """
                with self.satellite.lock:
                    payload = message['payload']
                    self.satellite.add_xlink_failure_info(payload)
                    self.sendResponse(key,target,True,waitForReply,payload)

            elif messageType == "START":  # Start sim
                """
                Wait until ground sends the START message to start the simulation.
                Once it does, send a response back immediately upon receipt and notify all threads. 
                """
                self.sendResponse(key, target,True,waitForReply)
                with self.sim_lock:
                    self.START_REQ = True
                    self.sim_lock.notify_all()

            elif messageType == "POST_RUN_REQ":
                """
                Ground requests post run information from satellite after entire simulation. 
                Sends all relevant information to ground and notifies all threads. 
                """
                with self.sim_lock and self.satellite.lock:
                    self.sendResponse(key, target,True,waitForReply)
                    self.post_run()
                    with self.sim_lock:
                        self.POST_RUN_REQ = True
                        self.sim_lock.notify_all()

            else:
                print("WARNING: Unknown message type.")

    def updateNextWindow(self,message:dict):
        """
        Updates this' next window uid based on message
        
        :param message      The incoming message
        """
        with self.satellite.lock:
            new_next_window_uid = message['payload']
            self.satellite.arbiter.plan_db.sat_windows_dict['next_window_uid'] = new_next_window_uid


    def post_run(self):
        """
        Generates post run information for satellite and sends information to ground
        Flags satellite as having ended simulation and notifies all other threads
        """
        postRunToSend = {'req_type':'POST_RUN','sender': self.sat_id, 'payload':{},'dest':'ground','waitForReply':True}
        payload = postRunToSend['payload']
        self.satellite.state_recorder.log_event(self.sim_end_dt,'Removed_Satellite.py','final_dv',[str(dc) for dc in self.satellite.state_sim.get_curr_data_conts()])

        payload['event_logs'] = self.satellite.state_recorder.get_events()
        payload['acts_exe'] = self.satellite.get_act_hist()
        payload['failures_exec'] = self.satellite.state_recorder.failed_dict['exec']
        payload['failures_nonexec'] = self.satellite.state_recorder.failed_dict['non-exec']
        payload['energy_usage'] = self.satellite.get_ES_hist()
        payload['data_usage'] = self.satellite.get_DS_hist()

        payload['cmd_update_hist'] = self.satellite.get_merged_cmd_update_hist(self.gs_id_order,self.gs_id_ignore_list)
        payload['end_time'] = self.satellite.sim_end_dt

        self.send_message(postRunToSend,target_id='ground')
        with self.sim_lock:
            self.END_SIM = True
            self.sim_lock.notify_all()

    def get_metrics_params(self):
        metrics_params = {}

        scenario_params = self.params['orbit_prop_params']['scenario_params']
        sat_params = self.params['orbit_prop_params']['sat_params']
        obs_params = self.params['orbit_prop_params']['obs_params']
        sim_metrics_params = self.params['const_sim_inst_params']['sim_metrics_params']
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
        


