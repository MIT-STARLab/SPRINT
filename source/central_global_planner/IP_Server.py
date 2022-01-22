import logging              
import sys, os, socket      
from threading import Thread
##
from OpenSSL import SSL # pip install pyOpenSSL
import queue
import pickle, json

from datetime import datetime
from circinus_tools  import time_tools as tt

DEFAULT_BUFF_SIZE = 32768

from sprint_tools.OEnum import PrintVerbosity

import struct
def encodeStrLen(msg, etype=">I"):
    return struct.pack(etype, len(msg) )

def decodeLen(buff, etype=">I"):
    return struct.unpack(etype,buff)[0]

# Implementation of the server for the CGP
class IP_Server(Thread):

    def __init__(self, port, log_pathName=None, printVerbose=PrintVerbosity.ALL):
        Thread.__init__(self)
        self.port = port

        # self.messages_to_pass = queue.Queue(0)
        self.messages_to_pass = [ queue.Queue(0) for n in range(0,4) ] # sim, sats[live conn], local, sats[not live conn] : high to lo priority
        self.outgoingMessageQueue = { 'sim' : queue.Queue(0) } # queue added for other dest-IDs when discovered

        self.printVerbose = printVerbose

        # self.queue_lock = False  For later, use this while clearing to prevent more incoming messages
        self.node_server = None
        self.SHUTDOWN_REQ = False

        self.logPathName = None
        if (log_pathName.rpartition('/')[0] != '' and log_pathName.rpartition('/')[2] != ''):
            if os.path.isdir(log_pathName.rpartition('/')[0]):
                self.logPathName = log_pathName
                self.__print_live("Logging at: {}".format(self.logPathName))
                logging.basicConfig(filename=self.logPathName, level=logging.DEBUG)
                logging.warn("Log started at: {}".format(self.logPathName))
        # else, log_pathName isFile

        if not self.logPathName:
            self.__print_live("Logging location invalid, NOT enabled.")

        self.latestGP = {
            "plan" : None,
            "windows" : None,
            "timestamp" : tt.date_string(datetime.now()),
            "pending" : False
        }

        self.act_timing_helper = None
        self.plan_db = None


    # vPri = level of verbose of the note ; must match or exceed instantiation setting 'printVerbose' for console print
    def __logNprint(self,note, vPri=PrintVerbosity.ALL):
        # printing
        if self.printVerbose != PrintVerbosity.NONE and vPri >= self.printVerbose:
            self.__print_live( str(note) )
        # logging
        if self.logPathName: logging.warn(note)

    def __print_live(self,str_to_print):
        print(str_to_print)
        sys.stdout.flush()

    def __dropClient(self,client_sock,errors=None):
        if errors:
            self.__print_live( 'Client %s left unexpectedly:' % (client_sock,) )
            self.__print_live( errors )
        else:
            self.__print_live( 'Client %s left politely' % (client_sock,) )
            client_sock.shutdown()
        client_sock.close()

    def __verify_cb(self,conn, cert, errnum, depth, ok):
        # self.__print_live( 'Got certificate: %s' % cert.get_subject() )
        return ok

    def setup_server(self):
        s_dir = 'certs'

        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.set_options(SSL.OP_NO_SSLv2)
        ctx.set_verify(SSL.VERIFY_PEER|SSL.VERIFY_FAIL_IF_NO_PEER_CERT, self.__verify_cb) # Demand a certificate
        ctx.use_privatekey_file  ( os.path.join(s_dir, 'Server.pkey') )
        ctx.use_certificate_file ( os.path.join(s_dir, 'Server.cert') )
        ctx.load_verify_locations( os.path.join(s_dir, 'CA.cert'    ) )

        bind_ip = '' # '0.0.0.0' # listen to all IP's...hence why we have SSL!
        bind_port = self.port   # ADMIN socket - 54201

        self.node_server = SSL.Connection(ctx, socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self.node_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.node_server.bind((bind_ip, bind_port)) 
        self.node_server.listen(5)  # max backlog of connections  # prob should correspond to number of clientss or a bit more

        self.__logNprint('Listening on {}:{}'.format(bind_ip, bind_port), PrintVerbosity.INFO)

    # considering making pri=-1 default, then picking highest priority if default
    def msg_avail(self, pri):
        if self.messages_to_pass[pri].qsize() > 0:
            return True
        else:
            return False

    def get_msg(self, pri=-1, strict=False):
        if pri == -1:
            for msg_queue in self.messages_to_pass:      # in increasing order
                if msg_queue.qsize() > 0:
                    return msg_queue.get()
        if self.messages_to_pass[pri].qsize() > 0:
            return self.messages_to_pass[pri].get()
        else:
            return None

    def clear_queue(self, pri): # use self.queue_lock if any chance of async incoming
        while self.msg_avail(pri):
            self.get_msg(pri)
        return self.messages_to_pass[pri].qsize()

    def get_name(self):
        return socket.gethostname()

    def run(self):
        self.setup_server()

        self.__logNprint("Server setup on: {}".format(self.port), PrintVerbosity.INFO)

        while not self.SHUTDOWN_REQ:
            client_sock, address = self.node_server.accept()  # This blocks. Need a timeout for shutdown flag to work
            self.handle_message(client_sock)

        self.__logNprint("Server ending...", PrintVerbosity.INFO)

        return
    

    # outputs basic parsed dictionary type, with trustworth fields
    # todo - validate all fields, perhaps from yaml definition of various structures
    def parse_msg(self, msg):
        # Parse
        retVal = { "PARSE_ERROR" : "UNPARSED" }  # in all cases should be changed

        serializer = 'pickle'
        retVal = {}
        try:
            try:
                retVal = pickle.loads(msg)
            except Exception:               # if pkl doesn't work
                try: 
                    retVal = json.loads(msg)
                    serializer = 'json'
                except:
                    self.__logNprint( "RX WARNING: Bad serialization format; neither JSON nor PICKLE worked.", PrintVerbosity.WARNINGS )

            # check for required keys, TODO: also validate their value types ; get list from config (ahead, not each time)
            if 'req_type' not in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "MISSING_KEY" : "req_type" }
            elif 'payload' not in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "MISSING_KEY" : "payload" }

            # prevent special terms from being used
            elif 'PARSE_ERROR' in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "INV_KEY" : "PARSE_ERROR" }

        except:
            retVal = { "PARSE_ERROR" : "INV_JSON" }


        if 'PARSE_ERROR' in retVal.keys():
            self.__logNprint( "RX WARNING: {}".format(retVal), PrintVerbosity.WARNINGS )

        return retVal, serializer


    #### Primary operational handler #####

    def handle_message(self, client_socket):
        START_MARKER = "size:".encode('ascii')
        rcv_buff = b''
        try:
            chunk = client_socket.recv(DEFAULT_BUFF_SIZE)
            if chunk.find(START_MARKER) < 0  or len(chunk) < len(START_MARKER)+4:  # bad start
                print("bad start chunk: ", chunk)
                self.__dropClient(client_socket)
                return
            
            len_start = chunk.find(START_MARKER)+len(START_MARKER)
            expectedFollowupLen = decodeLen( chunk[len_start:len_start+4] )

            rcv_buff = chunk[len_start+4:]
            rcv_buff = rcv_buff if len(rcv_buff) <= expectedFollowupLen else rcv_buff[:expectedFollowupLen]
            numRecv = len(rcv_buff)
            while ( numRecv < expectedFollowupLen and len(chunk) > 0): # and chunk != 'EOF'):
                chunk = client_socket.recv(DEFAULT_BUFF_SIZE)
                rcv_buff += chunk if len(chunk) <= (expectedFollowupLen-numRecv) else chunk[:numRecv-expectedFollowupLen]
                numRecv = len(rcv_buff)

            if numRecv != expectedFollowupLen:
                print("Warning, expected vs actual Bytes rx'd: {} vs {}".format(expectedFollowupLen, numRecv))
                self.__dropClient(client_socket)
                return

        except (SSL.WantReadError, SSL.WantWriteError, SSL.WantX509LookupError):
            return
        except SSL.ZeroReturnError:
            self.__dropClient(client_socket)
            return
        except(SSL.Error, errors):
            self.__dropClient(client_socket) #, errors)
            return

        
        req_dict, serializer = self.parse_msg(rcv_buff)
        if "PARSE_ERROR" in req_dict.keys():
            client_socket.send( pickle.dumps( { "NACK": req_dict } ) )
        else:
            data = None
            if (   req_dict['req_type'] == 'sim' ):
                self.messages_to_pass[0].put(req_dict)
                data = self.respondToNodeQuery(req_dict)
            elif ( req_dict['req_type'] == 'sat' ):
                # if sat has live contact:  # TODO - this check
                self.messages_to_pass[1].put(req_dict)
                # elif no live contact: pri=3/lowest
            elif ( req_dict['req_type'] == 'updateParams'):
                self.messages_to_pass[1].put(req_dict)
            elif ( req_dict['req_type'] == 'regenPlan'):
                self.messages_to_pass[1].put(req_dict)
                data = self.latestGP
            elif ( req_dict['req_type'] == 'updateWindows'):
                data = self.latestGP['windows']
            elif ( req_dict['req_type'] == 'reqPlan'):
                data = self.latestGP
            elif (req_dict['req_type'] == 'addSat'):
                self.messages_to_pass[1].put(req_dict)
            elif (req_dict['req_type'] == 'removeSat'):
                self.messages_to_pass[1].put(req_dict)
            elif (req_dict['req_type'] == 'updateSat'):
                self.messages_to_pass[1].put(req_dict)
            elif (req_dict['req_type'] == 'quit'):
                self.messages_to_pass[1].put(req_dict)
                exit()
    
            rsp_msg = { 
                "ACK"  : True ,
                "payload" : data
            }

            rsp_msg_B = pickle.dumps( rsp_msg ) if serializer=="pickle" else json.dumps( rsp_msg )
            toSend = len(rsp_msg_B)
            toSend_B = encodeStrLen(rsp_msg_B) # prev len()
            sentTot = 0
            header = START_MARKER+toSend_B
            client_socket.send(header)
            while( sentTot < toSend ):
                sentTot += client_socket.send( rsp_msg_B[sentTot:] )  # TODO - include message ID

        client_socket.close()

            # frc = free response count, the number of queued messages to include in a response; TODO - offer frs (fr-size) ; -1 is no limit
    def respondToNodeQuery(self, msg):

        response = {
            'frd' : [] # No free response data to start
        }

        if msg['req_type'] != 'sim': # NOT IMPLEMENTED FOR NON-SIM TYPES YET
            return response
        else:
            destID = 'sim'


        # Add first any pertinent requested info (updated plan, etc)
        cnt = msg['frc']
        if cnt == -1:
            cnt = self.outgoingMessageQueue[destID].qsize()

        for i in range(0,cnt):
            response['frd'] = response['frd'].append( self.outgoingMessageQueue[destID].get() )

