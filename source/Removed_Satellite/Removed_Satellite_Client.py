import logging  
import sys, os, socket
import pickle
import multiprocessing as mp
from queue import Empty
import time
DEFAULT_BUFF_SIZE = 32768
START_MARKER = "size:".encode('ascii')

import struct
def encodeStrLen(msg):
    return struct.pack(">I", len(msg))

def decodeLen(buff, etype=">I"):
    return struct.unpack(etype,buff)[0]


"""

The "sender" component of the removed satellite that connects and sends messages to recipient's server based on 
recipient id. 

It is structured such that it has one Process for each peer (other satellites + ground). Each Process
acts as a consumer for a message queue, sending messages as they come in based on the target ID and given 
connection. Each Process lives for the entirety of the simulation. 

"""
class RemovedSatelliteClient:
    def __init__(self,groundAddress,groundPort,msgsToSend:dict,path:str=None):

        """
        Creates a new RemovedSatelliteClient with no knowledge
        of any addresses besides ground

        :param groundAddress:   ip address of ground sim server
        :param groundPort       port used by ground sim server
        :param msgsToSend       empty dictionary for queues
        :param path             path for logging, sim_TestClient.log by default

        """

        if path:
            if (os.path.isdir(path+'/logs/')):
                self.logPath = path+'/logs/sim_TestClient.log'
        else:
            self.logPath = 'sim_TestClient.log'

        self.sat_id = None
        self.addressesByIDs = {"ground":(groundAddress,groundPort)}      # maps id's to ip addresses
        self.ordered_gs_ids = None                                       # ordered list of gs ids

        self.msgsToSend = msgsToSend
        self.msgsToSend['ground'] = mp.Queue()
        self.connections = {'ground': self.make_connection((groundAddress,groundPort))}
        self.processes = set()

        self.__print_live("Logging at: {}".format(self.logPath))
        logging.basicConfig(filename=self.logPath, level=logging.DEBUG)
        logging.warn("Log started at: {}".format(self.logPath))

    def __print_live(self,str_to_print):
        print(str_to_print)
        sys.stdout.flush()

    ###################################################################################################################
    #                                           CONNECTION-BASED FUNCTIONS                                            #
    ###################################################################################################################

    def make_connection(self,address:tuple):
        """
        Creates socket connection to given address
        :param   address: A tuple in the form (<hostname>,<port num>)
        :return: The socket connection
        """
        RETRY_NUM = 100
        num_retry = 0

        while num_retry < RETRY_NUM:
            try:
                connection = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                connection.connect(address)
                return connection
            except socket.error:
                print(f"Failed to connect to {address}. Retrying in 1 second.")
                time.sleep(1)
            num_retry += 1

        raise Exception(f"Unable to connect to {address} after {RETRY_NUM} tries every second.")

    def set_ips(self,all_ips:dict):
        """
        Sets addresses for all peers' servers, and establishes connections
        with all satellites and ground sim

        :param all_ips: All ips to register as a dictionary
        """
        for k in all_ips:
            self.addressesByIDs[k] = all_ips[k]

        del self.addressesByIDs[self.sat_id]

        # Establish connections
        self.set_connections(self.addressesByIDs)

        # Set up queues for connections
        self.set_queues(list(self.addressesByIDs.keys()))

        # Start one daemon thread for each connection
        for targ_id in self.addressesByIDs:
            if targ_id != 'ground':
                p = mp.Process(target = self.run,args=(targ_id,self.connections[targ_id],
                                                       self.msgsToSend[targ_id]),daemon=True)
                self.processes.add(p)
                p.start()


    def set_connections(self,all_ips:dict):
        """
        Sets up all connections to all other peers
        :param all_ips : The dictionary mapping agent IDs to IP addresses

        """
        for s in all_ips:
            if s != 'ground':
                self.connections[s] = self.make_connection(all_ips[s])


    def start_ground_connection(self):
        """
        Starts connection and running daemon thread with ground
        """
        import time
        try:
            p = mp.Process(target = self.run,args=('ground',self.connections['ground'],
                                                   self.msgsToSend['ground']),daemon=True)
            self.processes.add(p)
            p.start()
        except:
            print("\n\n\n <CLIENT> {}PROBLEM WITH CLIENT FOR GROUND".format(time.time()))


    ###################################################################################################################
    #                                            MESSAGE PASSING FUNCTIONS                                            #
    ###################################################################################################################
    def set_queues(self,peers:list):
        """
        Updates message queues for each peer, where all ground stations are collectively referred to as ground

        :param peers: The list of peer IDs, not including GS IDs
        """
        for p in peers:
            if p != 'ground':
                self.msgsToSend[p] = mp.Queue(0)

    def haveMsgToSend(self,targ_id:str):
        """
        Returns whether there is message to send or not given target id
        :param targ_id: The target ID
        :return: True if there is a message to send, False otherwise
        """
        return self.msgsToSend[targ_id].qsize() > 0

    def getMessage(self,targ_id:str):
        """
        Gets message off of given id's queue
        :param <str> targ_id: The id of the target
        :return: A dictionary message, if any are in the queue
        """
        try:
            msg = self.msgsToSend[targ_id].get()
            return msg
        except Empty:
            return None

    ###################################################################################################################
    #                                               MAIN CLIENT FUNCTIONS                                            #
    ###################################################################################################################

    def run(self,targ_id:str,connection:socket.socket,msgsToSend:mp.Queue):
        """
        Main loop for maintaining connection and sending messages

        :param targ_id:     The ID of the target
        :param connection:  The corresponding socket
        :param msgsToSend:  The queue it will consume to send messages
        """

        try:
            while(True):

                msg = msgsToSend.get()
                bytes = pickle.dumps(msg)
                self.transmit(targ_id,connection,bytes)

        except Exception as e:
            print("PROBLEM WITH CLIENT")


    def transmit(self,targ_id:str,client:socket.socket,bytes_tx:bytes):
        """
        Transmits the given bytes to the IP address of targ_id

        Starts transmitting a packet header in the format:
        START_MARKER --> length of message in bytes

        Then sends the message in chunks

        :param <str>    targ_id:         The id of the target
        :param <socket> client:          The connection
        :param <bytes>  bytes_tx:        The bytes to send

        """
        START_MARKER = "size:".encode('ascii')
        MAX_TRIES = 3

        for i in range(MAX_TRIES):
            try:

                toSend   = len(bytes_tx)

                # Send header
                client.send(START_MARKER + encodeStrLen(bytes_tx))
                sentTot = 0

                # Send rest of message
                while sentTot < toSend:
                    sentTot += client.send(bytes_tx[sentTot:])

                try:
                    parseable = self.receive_response(client)
                    if parseable:
                        return

                except:
                    print("<CLIENT> Error Receiving: {}:{}".format(targ_id, self.addressesByIDs[targ_id]))
                    logging.warn("<CLIENT>Error Receiving: {}:{}".format(targ_id, self.addressesByIDs[targ_id]))

            except:
                print       ("<CLIENT>Error Transmitting to: {}".format(targ_id))
                logging.warn("<CLIENT>Error Transmitting to: {}".format(targ_id))

        print("<CLIENT> EXCEEDED MAX NUMBER OF TRIES ({}) TO TRANSMIT MESSAGE".format(MAX_TRIES))


    def receive_response(self,client:socket.socket):
        """
        Receives PARSEABLE response from server
        :param client: The connection
        :return: True if successful transmission, False otherwise
        """

        rcv_buff = b''
        chunk = client.recv(DEFAULT_BUFF_SIZE)
        len_start = chunk.find(START_MARKER) + len(START_MARKER)
        expectedFollowupLen = decodeLen(chunk[len_start:len_start + 4])
        rcv_buff += chunk[len_start + 4:]
        numRecv = len(rcv_buff)

        while (numRecv < expectedFollowupLen and len(chunk) > 0):  # and chunk != 'EOF'):

            chunk = client.recv(DEFAULT_BUFF_SIZE)
            rcv_buff += chunk
            numRecv = len(rcv_buff)

        rsp_msg = pickle.loads(rcv_buff)

        return rsp_msg['PARSEABLE']

    def set_gs_ids(self,gs_ids:list):
        """
        Sets this' gs ids to gs_ids.
        Assumes gs_ids is ordered by index
        :param list gs_ids: List of gs_ids
        """
        self.ordered_gs_ids = gs_ids

    def set_id(self,id:str):
        self.sat_id = id

if __name__ == "__main__":
    pass

