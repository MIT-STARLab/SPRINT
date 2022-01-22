import sys, socket
import pickle
import multiprocessing as mp

DEFAULT_BUFF_SIZE = 32768

import struct
def encodeStrLen(msg):
    return struct.pack(">I", len(msg) )
def decodeLen(buff, etype=">I"):
    return struct.unpack(etype,buff)[0]

"""
The message sender of Ground Sim, handling all sending for all ground stations. 

This Client is structured such that for each satellite, it produces a Process that acts as a consumer in a message queue
and transmits the message given the connection it is initialized with. These Processes continue for the entirety of
the simulation. 

"""
class GroundClient:
    EXPECTED_ACKNOWLEDGEMENT_REPLY = {"ACK": True, "payload": None} # base expected reply from server
    
    def __init__(self,messagesToSend:dict):
        """
        Constructor
        :param messagesToSend: Dictionary mapping target to message Queue
        """
        self.client = None
        self.messagesToSend = messagesToSend    # The queue to receive messages

        self.ips_by_id = {}         # Maps ID of satellites to their servers' IP addresses
        self.connections = {}       # Active connections with satellite servers
        self.processes = {}         # The processes using the active connections
        self.idCount = 0            # ID count used to assign messages unique IDs


    ###################################################################################################################
    #                                           CONNECTION-BASED FUNCTIONS                                            #
    ###################################################################################################################

    def make_connection(self,address:tuple):
        """
        Creates socket connection to given address
        :param   address: A tuple in the form (<hostname>,<port num>)
        :return: The socket connection
        """
        connection = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        print("<CLIENT> connecting to ",address)
        connection.connect(address)
        return connection

    def add_id(self,id:str,address,port):
        """
        Registers id to be located at address. Overwrites if necessary.
        Also starts a connection with the given address and associates it with
        the given id
        """
        # Record address
        self.ips_by_id[id] = (address,port)

        # Initialize message queue
        self.messagesToSend[id] = mp.Queue(0)

        # Initialize connections
        self.connections[id] = self.make_connection((address,port))

        # Start process
        process = mp.Process(target = self.run,args=(id,self.connections[id],self.messagesToSend[id]),daemon=True)
        self.processes[id] = process
        process.start()
    
    def remove_id(self,id:str):
        """
        Removes the given ID from known addresses and connections
        :param id: The ID of the agent
        """
        del self.ips_by_id[id]

        # Stop Process
        self.processes[id].terminate()
        del self.processes[id]

        # Stop connection
        self.connections[id].close()
        del self.connections[id]

    
    def get_addresses(self):
        return self.ips_by_id.keys()
        
    def __print_live(self,str_to_print):
        print(str_to_print)
        sys.stdout.flush()
    
    def get_name(self):
        """
        Returns host name of this.
        """
        return socket.gethostname()
    
    def get_address(self):
        """
        Returns IP address of this.
        """
        return socket.gethostbyname(self.get_name())


    def run(self,targ_id:str,connection:socket.socket,msgsToSend:mp.Queue):
        """
        Main running loop of client

        :param targ_id:     The ID of the target
        :param connection:  The connection to use to send messages
        :param msgsToSend:  The queue to use to receive messages to send
        """

        while(True):
            # Receive and serialize message
            msg = msgsToSend.get()
            bytes = pickle.dumps(msg)

            # Send message
            self.transmit(targ_id,connection,bytes)

    def transmit(self,targ_id:str,client:socket.socket,bytes_tx:bytes):
        """
        Transmits bytes to satellite with specified id
        Adds a message header in format:
        START_MARKER --> length of message in bytes

        :param targ_id      Satellite ID to send to
        :param client       The socket connection to the ID's server
        :param bytes_tx     The message to send in bytes

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
                    print("<CLIENT> Error Receiving: {}".format(targ_id))

            except:
                print       ("<CLIENT> Error Transmitting to: {}".format(targ_id))

        print("<CLIENT> EXCEEDED MAX NUMBER OF TRIES ({}) TO TRANSMIT MESSAGE".format(MAX_TRIES))

    def receive_response(self,client:socket.socket):
        """
        Receives PARSEABLE response from server
        :param client: The connection
        :return: True if successful transmission, False otherwise
        """
        START_MARKER = "size:".encode('ascii')

        # Receive header and decode message length
        rcv_buff = b''
        chunk = client.recv(DEFAULT_BUFF_SIZE)
        len_start = chunk.find(START_MARKER) + len(START_MARKER)
        expectedFollowupLen = decodeLen(chunk[len_start:len_start + 4])
        rcv_buff += chunk[len_start + 4:]
        numRecv = len(rcv_buff)

        # Receive up to message length or until message ends,
        # whichever comes first
        while (numRecv < expectedFollowupLen and len(chunk) > 0):  # and chunk != 'EOF'):

            chunk = client.recv(DEFAULT_BUFF_SIZE)
            rcv_buff += chunk
            numRecv = len(rcv_buff)

        rsp_msg = pickle.loads(rcv_buff)

        return rsp_msg['PARSEABLE']



if __name__ == "__main__":
    pass

