import sys, socket
from OpenSSL import SSL
import pickle, json
import select
DEFAULT_BUFF_SIZE = 32768
from sprint_tools.OEnum import PrintVerbosity
import struct
def encodeStrLen(msg, etype=">I"):
    return struct.pack(etype, len(msg) )

def decodeLen(buff, etype=">I"):
    return struct.unpack(etype,buff)[0]

"""
A component of RemovedSatellite that receives incoming messages, passes these messages to the RemovedSatellite, and 
sends ACK (or NACK) messages to sender 

"""

class RemovedSatelliteServer:

    def __init__(self,connection):

        self.connection = connection

        self.server = None              # Actual server object
        self.selector = None            # Selector used to receive messages
        self.SHUTDOWN_REQ = False
        self.clients = set()
        self.inputs = []
        self.addresses = set()

        self.act_timing_helper = None
        self.port = None
        self.setup_server()
        self.run()

    ###################################################################################################################
    #                                         INITIALIZATION-BASED FUNCTIONS                                          #
    ###################################################################################################################

    def setup_server(self):
        """
        Initializes server SSL connection, loading server parameters and
        authenticating connection using certificates under central_global_planner/certs.

        Directions to set up certificates: https://dst.lbl.gov/~boverhof/openssl_certs.html
            - NOTE: Use 2048, not 1024, to make certificates
            - NOTE: Use .cert instead of .pem, and .pkey instead of .key
            - NOTE: Same CA.cert must be on all running devices for authentication
        """
        bind_ip = ''                                    # Use host IP

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setblocking(0)
        self.server.bind((bind_ip, 0))                  # Dynamically assign server socket
        self.server.listen()                            # Currently unlimited capacity
        self.port = self.server.getsockname()[1]
        self.connection.send(("SERVER_PORT",self.port))

    def get_name(self):
        return socket.gethostname()

    def get_address(self):
        return socket.gethostbyname(self.get_name())

    ###################################################################################################################
    #                                           CONNECTION-BASED FUNCTIONS                                            #
    ###################################################################################################################

    def run(self):
        """
        Runs the server as background thread to listen to a specific socket

        Continuously listens to existing connections/sockets, and also registers
        new connections as they come.

        """
        print("<SERVER> Server setup on: {}".format(self.port))

        try:
            self.inputs  = [self.server] # Sockets to read from
            outputs = []            # Sockets to write to (none, in this case)

            while not self.SHUTDOWN_REQ:
                readable,writable,exceptional = select.select(self.inputs,outputs,self.inputs)

                for s in readable:
                    if s is self.server:
                        # Readable server accepting new connection
                        connection,client_address = s.accept()
                        connection.setblocking(0)
                        self.inputs.append(connection)
                    else:
                        # Known connection is sending data
                        self.receive_message(s)

                for s in exceptional:
                    # Stop listening to socket if there is an exception
                    self.inputs.remove(s)
                    s.close()

            print("Ending server")

        except Exception as e:
            # print("<SERVER> ERROR IN SERVER")
            print("ERROR TYPE:", type(e))
            print(e)

    def __print_live(self,str_to_print):
        print(str_to_print)
        sys.stdout.flush()

    def __dropClient(self,client_sock:socket.socket,errors=None):
        if errors:
            self.__print_live( 'Client %s left unexpectedly:' % (client_sock,) )
            self.__print_live( errors )
        else:
            self.__print_live( 'Client %s left politely' % (client_sock,) )
            self.inputs.remove(client_sock)
            client_sock.shutdown(socket.SHUT_RDWR)
        client_sock.close()


    def parse_msg(self, msg:bytes):
        """
        Parses the given message and determine if the message is valid
        :param msg: Incoming message
        :return: Parsed message, serializer used
        """
        retVal = { "PARSE_ERROR" : "UNPARSED" }  # in all cases should be changed

        serializer = 'pickle'
        retVal = {}
        try:
            try: # try to use pickle
                retVal = pickle.loads(msg)

            except Exception:  # if pkl doesn't work, use json
                print("<SERVER> Unable to unpickle message")
                try: 
                    retVal = json.loads(msg)
                    serializer = 'json'
                except:
                    print( "<SERVER> RX WARNING: Bad serialization format; neither JSON nor PICKLE worked.", PrintVerbosity.WARNINGS )

            # check for required keys
            if 'req_type' not in retVal.keys() and 'ACK' not in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "MISSING_KEY" : "req_type or ACK" }

            elif 'payload' not in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "MISSING_KEY" : "payload" }

            elif 'id' not in retVal.keys():
                retVal = {'PARSE_ERROR' : 'INV_STRUCT', "MISSING_KEY": "id"}

            # prevent special terms from being used
            elif 'PARSE_ERROR' in retVal.keys():
                retVal = { "PARSE_ERROR" : "INV_STRUCT" , "INV_KEY" : "PARSE_ERROR" }

        except:
            retVal = { "PARSE_ERROR" : "INV_JSON" }


        if 'PARSE_ERROR' in retVal.keys():
            print( "<PRINT> RX WARNING: {}".format(retVal))


        return retVal, serializer


    def receive_message(self, client_socket:socket.socket):
        """
        Receives message chunks given socket, putting message
        into queue if valid

        Sends a reply message:
        NACK: message could not be parsed
        ACK : True if message parseable and valid, False if unknown message type

        :param client_socket: The input connection
        """
        client_socket.setblocking(True)

        START_MARKER = "size:".encode('ascii')
        try:
            chunk = client_socket.recv(DEFAULT_BUFF_SIZE)

            # Assert start of message is valid header
            if chunk.find(START_MARKER) < 0  or len(chunk) < len(START_MARKER)+4:  # bad start
                print("<SERVER> bad start chunk: ", chunk)

                self.__dropClient(client_socket)
                return


            # Determine message length based on header
            len_start = chunk.find(START_MARKER)+len(START_MARKER)
            expectedFollowupLen = decodeLen( chunk[len_start:len_start+4] )

            # Get any part of message that was sent with header, if any
            rcv_buff = chunk[len_start+4:]
            rcv_buff = rcv_buff if len(rcv_buff) <= expectedFollowupLen else rcv_buff[:expectedFollowupLen]
            numRecv = len(rcv_buff)

            # Continue to receive chunks until get all expected bytes
            while numRecv < expectedFollowupLen and len(chunk) > 0 and chunk != 'EOF':

                try:
                    chunk = client_socket.recv(DEFAULT_BUFF_SIZE)

                    rcv_buff += chunk if len(chunk) <= (expectedFollowupLen-numRecv) else chunk[:numRecv-expectedFollowupLen]
                    numRecv = len(rcv_buff)
                except:
                    print("<SERVER> CANT RECEIVE CLIENT CHUNK")


            # Drop client if message is not required length
            if numRecv != expectedFollowupLen:
                print("Warning, expected vs actual Bytes rx'd: {} vs {}".format(expectedFollowupLen, numRecv))
                self.__dropClient(client_socket)
                return

        except (SSL.WantReadError, SSL.WantWriteError, SSL.WantX509LookupError):
            print("<SERVER> SSL ERROR 1")
            return
        except SSL.ZeroReturnError:
            self.__dropClient(client_socket)
            print("<SERVER> SSL ZERO RETURN ERROR")
            return
        except(SSL.Error):
            self.__dropClient(client_socket)
            print("<SERVER> SSL GENERIC ERROR")
            return
        except Exception as e:
            print(e)
            return



        # Parse message
        message, serializer = self.parse_msg(rcv_buff)

        if "PARSE_ERROR" in message.keys():
            # If we have enough information to send a NACK, do so
            try:
                self.sendParseResponse(False,client_socket)
            except:
                print("FAILED TO SEND PARSEABLE FEEDBACK. Waiting for message again")

        else: # Handle incoming message and send ACK

            try:
                self.sendParseResponse(True,client_socket)
            except:
                print("FAILED TO SEND PARSEABLE FEEDBACK. Waiting for message again.")
                client_socket.setblocking(True)
                return

            possibleSimMessages = {'START','PLAN','BDT','STATES','UPDATE','NEXT_WINDOW_UPDATE',
                                   'ALL_IPS','INJECT_OBS','SAT_WINDOWS_INIT','INIT_PARAMS',
                                   'ACTS_DONE','FINISHED_PROP','READY_FOR_TIME_UPDATE','XLINK_FAILURE',
                                   'POST_RUN_REQ'}

            if 'req_type' in message:
                messageType = message['req_type']
                if messageType in possibleSimMessages:
                    self.connection.send(message)
                elif messageType == 'quit': exit()

            elif 'ACK' in message:
                # If message is ACK...

                success = message['ACK']
                _id = message['id']

                payload = message['payload']
                waitForReply = message['txWaitForReply']

                if payload:
                    ## If there is a payload attached, send the payload
                    self.connection.send(("ACK",_id,payload,waitForReply))
                else:
                    ## If there is no payload, send success boolean
                    self.connection.send(("ACK",_id,success,waitForReply))
            else:
                print("UNKNOWN MESSAGE TYPE")

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

        client.send(START_MARKER + encodeStrLen(response_bytes))

        sentTot = 0
        while sentTot < numBytes:
            sentTot += client.send(response_bytes[sentTot:])

if __name__ == "__main__":
    pass

