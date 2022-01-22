import sys, socket
from threading import *
from OpenSSL import SSL
import queue,select
import pickle, json
from Removed_Satellite.BlockingDict import BlockingDict
import multiprocessing as mp
DEFAULT_BUFF_SIZE = 32768
import multiprocessing.connection as mpc
import struct
def encodeStrLen(msg, etype=">I"):
    return struct.pack(etype, len(msg) )

def decodeLen(buff, etype=">I"):
    return struct.unpack(etype,buff)[0]


"""

Implementation of the server for Ground Server. Holds orbit propagation and link calculations, and 
sends the data to clients

"""

class GroundServer:

    def __init__(self,port:int,numSats:int,conn:mpc.Connection):
        self.connection = conn
        self.port = port
        self.responses = BlockingDict()
        self.messages_to_pass = mp.Queue(0)    # unlimited length. Messages to pass to controller
        self.inputs = []
        self.server = None
        self.SHUTDOWN_REQ = False


        self.numSats = numSats                 # number of satellites expected
        self.numSatsJoined = 0                 # number of satellites actually joined
        self.serverLock = RLock()              # Lock on server contents

        self.setup_server()
        self.run()

    def __print_live(self,str_to_print):
        print(str_to_print)
        sys.stdout.flush()

    def __dropClient(self,client_sock,errors=None):
        if errors:
            self.__print_live( 'Client %s left unexpectedly:' % (client_sock,) )
            self.__print_live( errors )
        else:
            self.__print_live( 'Client %s left politely' % (client_sock,) )
            self.inputs.remove(client_sock)
            client_sock.shutdown(socket.SHUT_RDWR)
        client_sock.close()

    def setup_server(self):
        """
        Initializes server SSL connection, loading server parameters and
        authenticating connection using certificates under central_global_planner/certs.
        
        Directions to set up certificates: https://dst.lbl.gov/~boverhof/openssl_certs.html
            - NOTE: Use 2048, not 1024, to make certificates
            - NOTE: Use .cert instead of .pem, and .pkey instead of .key
            - NOTE: Same CA.cert must be on all running devices for authentication
        """

        bind_ip = ''            # Use host IP address
        bind_port = self.port   # ADMIN socket - 54201

        self.server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((bind_ip, bind_port))
        self.server.listen()

        print('<SERVER> Listening on {}:{}'.format(bind_ip, bind_port))
    
    def get_num_sats_to_join(self):
        """
        Returns number of satellites left to join before simulation to run
        0 indicates all satellites have joined
        """
        with self.serverLock:
            return self.numSats - self.numSatsJoined

    def msg_avail(self):
        """
        Determines if there is a message available
        :return: True if yes, false otherwise
        """
        if self.messages_to_pass.qsize() > 0:
            return True
        else:
            return False
    
    def get_message(self, block = True, timeOut = None):
        """
        Gets the current message in FIFO order

        @block: boolean. True if block until queue nonempty, False otherwise
        @timeOut: number of seconds to block before Empty exception raised (giving up on waiting for message)
        """
        try:
            return self.messages_to_pass.get(block = block, timeout = timeOut )
        except queue.Empty:
            return None

    def get_response(self,msgId:str):
        """
        Gets response to message with id msgId
        :param msgId: ID of the message
        :return: True/False, or the message's payload
        """
        return self.responses.get(msgId)

    def clear_queue(self): # use self.queue_lock if any chance of async incoming
        while self.msg_avail():
            self.get_message()
        return self.messages_to_pass.qsize()

    def get_name(self):
        return socket.gethostname()
        
    def get_address(self):
        return socket.gethostbyname(self.get_name())

        
    def run(self):
        self.setup_server()

        print("Server setup on: {}".format(self.port))

        self.inputs = [self.server]
        outputs = []

        while not self.SHUTDOWN_REQ:
            readable,writable,exceptional = select.select(self.inputs,outputs,self.inputs)

            for s in readable:
                if s is self.server:
                    # Readable server accepting new connections and
                    # establishing satellites
                    connection,client_address = s.accept()
                    connection.setblocking(0)
                    self.inputs.append(connection)

                    # Check for joining
                    self.receive_message(connection,address = client_address)

                else:
                    # Known connection is sending data
                    self.receive_message(s)

            for s in exceptional:
                # Stop listening to socket if there is an exception
                print("Handling exceptional socket connection for {}".format(s.getpeername()))
                self.inputs.remove(s)
                s.close()

        print("Server ending...")
    

    # outputs basic parsed dictionary type, with trustworth fields
    def parse_msg(self, msg):
        """
        Parses the incoming message and checks that it is valid
        :param msg: Incoming message
        :return: Parsed message and serializer used
        """

        serializer = 'pickle'
        retVal = {}
        try:
            try: # Try to use pickle
                retVal = pickle.loads(msg)
            except Exception:
                try:
                    # Try to use json
                    retVal = json.loads(msg)
                    serializer = 'json'
                except:
                    print( "RX WARNING: Bad serialization format; neither JSON nor PICKLE worked.")

            # check for required keys,
            if 'req_type' not in retVal.keys() and 'ACK' not in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "MISSING_KEY" : "req_type or ACK" }
            elif 'payload' not in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "MISSING_KEY" : "payload" }

            # prevent special terms from being used
            elif 'PARSE_ERROR' in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "INV_KEY" : "PARSE_ERROR" }

        except:
            retVal = { "PARSE_ERROR" : "INV_JSON" }


        if 'PARSE_ERROR' in retVal.keys():
            print( "RX WARNING: {}".format(retVal))

        return retVal, serializer

    
    #### Primary operational handler #####

    def receive_message(self,client_socket:socket.socket,address = None):
        """
        Receives incoming message in chunks given socket

        If message is valid and parsed, adds it to queue

        Sends a response message:
        NACK: unparseable
        ACK: True if parseable and recognized message type, False otherwise

        :param client_socket: The incoming socket
        :param address: IP address of port. Provided only for new connections
        """

        client_socket.setblocking(True)
        # Get Message in chunks
        START_MARKER = "size:".encode('ascii')
        rcv_buff = b''
        try:
            chunk = client_socket.recv(DEFAULT_BUFF_SIZE)
            # Check that message starts with header
            if chunk.find(START_MARKER) < 0  or len(chunk) < len(START_MARKER)+4:  # bad start
                print("bad start chunk: ", chunk)
                client_socket.setblocking(False)
                self.inputs.remove(client_socket)
                return

            # Extract expected message length from header
            len_start = chunk.find(START_MARKER)+len(START_MARKER)
            expectedFollowupLen = decodeLen( chunk[len_start:len_start+4] )

            # Get any message sent with header
            rcv_buff = chunk[len_start+4:]
            rcv_buff = rcv_buff if len(rcv_buff) <= expectedFollowupLen else rcv_buff[:expectedFollowupLen]
            numRecv = len(rcv_buff)

            # Get rest of message in chunks
            while ( numRecv < expectedFollowupLen and len(chunk) > 0): # and chunk != 'EOF'):
                chunk = client_socket.recv(DEFAULT_BUFF_SIZE)
                rcv_buff += chunk if len(chunk) <= (expectedFollowupLen-numRecv) else chunk[:numRecv-expectedFollowupLen]
                numRecv = len(rcv_buff)

            # Throw error if we did NOT receive the expected amount of data
            if numRecv != expectedFollowupLen:
                print("Warning, expected vs actual Bytes rx'd: {} vs {}".format(expectedFollowupLen, numRecv))
                self.__dropClient(client_socket)
                client_socket.setblocking(False)
                return

        except (SSL.WantReadError, SSL.WantWriteError, SSL.WantX509LookupError):
            client_socket.setblocking(False)
            return
        except SSL.ZeroReturnError:
            self.__dropClient(client_socket)
            client_socket.setblocking(False)
            return
        except(SSL.Error):
            self.__dropClient(client_socket) #, errors)
            client_socket.setblocking(False)
            return

        message, serializer = self.parse_msg(rcv_buff)
        if "PARSE_ERROR" in message.keys():
            try:
                self.sendParseResponse(False,client_socket)
            except: print("<SERVER> FAILED TO SEND PARSEABLE FEEDBACK")

        else:
            try:
                self.sendParseResponse(True,client_socket)
            except:
                print("<SERVER> FAILED TO SEND PARSEABLE FEEDBACK")
                client_socket.setblocking(False)
                return


            if 'req_type' in message:
                messageType = message['req_type']
                if messageType == 'JOIN':
                    # For establishing NEW connections only

                    if self.get_num_sats_to_join() > 0:
                        self.__print_live("Satellite joining from {}.".format(client_socket.getpeername()))
                        message['payload']['address'] = client_socket.getpeername()[0]
                        self.connection.send(("JOIN",message))
                        self.numSatsJoined += 1
                    else:
                        self.__print_live("Extra join code. Unacknowledged.")

                elif not address:
                    # Main simulation messages
                    # These should have addresses already defined

                    if messageType in {'PLAN','BDT','ACTS_DONE','FINISHED_PROP',
                                        'READY_FOR_TIME_UPDATE','SAT_STATS','POST_RUN'}:
                        self.connection.send(message)

                    elif messageType == 'quit': exit()

            elif 'ACK' in message:

                _id = message['id']
                success = message['ACK']
                payload = message['payload']
                waitForReply = message['txWaitForReply']
                if payload:
                    self.connection.send(("ACK",_id,payload,waitForReply))
                else: self.connection.send(("ACK",_id,success,waitForReply))

            client_socket.setblocking(False)

    def sendParseResponse(self,parseable:bool,client:socket.socket):
        """
        Sends response to client for whether the message was parseable.

        :param parseable: True if parseable, False if not
        :param client: The connection
        """
        START_MARKER = "size:".encode('ascii')

        response_bytes = pickle.dumps({'PARSEABLE':parseable})
        numBytes = len(response_bytes)

        # Send header
        client.send(START_MARKER + encodeStrLen(response_bytes))

        sentTot = 0
        while sentTot < numBytes:
            sentTot += client.send(response_bytes[sentTot:])

if __name__ == "__main__":
    pass


