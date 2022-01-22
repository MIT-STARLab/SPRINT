import logging
import sys, os, socket
import pickle
from OpenSSL import SSL # pip install pyOpenSSL

import pathlib

DEFAULT_BUFF_SIZE = 32768

import struct
def encodeStrLen(msg):
    return struct.pack(">I", len(msg) )
def decodeLen(buff, etype=">I"):
    return struct.unpack(etype,buff)[0]

class IP_Client:
    def __init__(self, ips_by_id, targ_port, path=None):
        self.port = targ_port
        if (os.path.isdir(path+'/logs/')):
            self.logPath = path+'/logs/sim_TestClient.log'
        else:
            self.logPath = 'sim_TestClient.log'

        self.node_client = None

        self.ips_by_id = ips_by_id

        self.__print_live("Logging at: {}".format(self.logPath))
        logging.basicConfig(filename=self.logPath, level=logging.DEBUG)
        logging.warn("Log started at: {}".format(self.logPath))


    def __print_live(self,str_to_print):
        print(str_to_print)
        sys.stdout.flush()

    @staticmethod
    def verify_cb(conn, cert, errnum, depth, ok):
        # print_live('Got certificate: %s' % cert.get_subject())
        return ok

    def __setup_client(self): #, cur_path=""):
        # print(pwd)
# pathlib.Path(__file__).parent.absolute()+
        # c_dir = 'certs'  # generated with 
        # if cur_path != "":
        c_dir = os.getcwd() + '/../../central_global_planner/certs' # + c_dir


        # Initialize context

        # import ipdb
        # ipdb.set_trace()


        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.set_verify(SSL.VERIFY_PEER, self.verify_cb) # Demand a certificate
        # print("trying to use: ",os.path.join(c_dir, 'client.pkey'))
        ctx.use_privatekey_file  ( os.path.join(c_dir, 'Client.pkey') )
        ctx.use_certificate_file ( os.path.join(c_dir, 'Client.cert') )
        ctx.load_verify_locations( os.path.join(c_dir, 'CA.cert')     )
    
        self.node_client = SSL.Connection(ctx,  socket.socket(socket.AF_INET, socket.SOCK_STREAM) )



    def transmit(self,targ_id,bytes_tx):
        # print("TX {} bytes".format( len(bytes_tx) )) 
        if targ_id not in self.ips_by_id:
            print("ERR: targ_id not in self.ips_by_id")
            return None

        START_MARKER = "size:".encode('ascii')
        rcv_buff = b''
        try:
            self.__setup_client()   # Setting up & tearing down seems to be necessary to use the same overall client wrapper for different server IPs; that, or maintain a connection for each
            self.node_client.connect((self.ips_by_id[targ_id], self.port))
            toSend   = len(bytes_tx)

            self.node_client.send(START_MARKER+encodeStrLen(bytes_tx))
            sentTot = 0
            while( sentTot < toSend ):
                sentTot += self.node_client.send(bytes_tx[sentTot:])

            try:
                chunk = self.node_client.recv(DEFAULT_BUFF_SIZE)

                len_start = chunk.find(START_MARKER)+len(START_MARKER)
                expectedFollowupLen = decodeLen( chunk[len_start:len_start+4] )
                rcv_buff += chunk[len_start+4+1:]
                numRecv = len(rcv_buff)

                while ( numRecv < expectedFollowupLen and len(chunk) > 0): # and chunk != 'EOF'):
                    chunk = self.node_client.recv(DEFAULT_BUFF_SIZE)
                    rcv_buff += chunk
                    numRecv = len(rcv_buff)

                self.node_client.shutdown()
                return rcv_buff

            except:
                print       ("Error Receiving: {}:{}".format(targ_id, self.ips_by_id[targ_id]))
                logging.warn("Error Receiving: {}:{}".format(targ_id, self.ips_by_id[targ_id]))

        except:
            print       ("Error Transmitting: {}:{}".format(targ_id, self.ips_by_id[targ_id]))
            logging.warn("Error Transmitting: {}:{}".format(targ_id, self.ips_by_id[targ_id]))

        self.node_client.shutdown()
        return rcv_buff

    def broadcast(self, bytes_tx):
        for targ_id in self.ips_by_id.keys():
            self.transmit(targ_id, bytes_tx)



if __name__ == "__main__":
    client = IP_Client({"cgp":"localhost"},54202,".")

    tstMsg = { 
                'st':'sim', 
                'pl': {
                    'tp':'setup',           # tp = sim msg type
                    'data': {
                        'cfgSrc':'CIRCINUS',    # circinus legacy-type setup
                        'preComputed' : {
                            "propData" : None,
                            "linkData" : None,
                            "stnData"  : None
                        },
                        'configDict' : {    # needs to come from cur sim cfg structure                       
                            'orbit_prop_params' : {'gs_params' : {'gs_network_name':None,'gs_id_order' : []},'sat_params' : {'activity_params' : None,'sat_id_order'    : None},'orbit_params' : { 'sat_ids_by_orbit_name' : {} } },
                            'num_sats' : None,
                            'const_sim_inst_params' : {'sim_run_params' : {'start_utc_dt' : None,'end_utc_dt'   : None}, 'sim_gs_network_params' : {'gsn_ps_params': { 'replan_interval_s': 6300,'replan_release_wait_time_s': 60, 'release_first_plans_immediately': True }, 'time_epsilon_s':1 }}
                        }
                    }
                },
                'frc': -1
            }  # st:source type | pl:payload
    client.transmit( "cgp", pickle.dumps(tstMsg) )
    tstMsg = { 'st':'sat', 'pl':'TESTMSG-2' }  # st:source type | pl:payload
    client.transmit( "cgp", pickle.dumps(tstMsg) )
    tstMsg = { 
                'st':'sim', 
                'pl': {
                    'tp':'other',
                    'data':'datablob'
                },
                'frc': -1
        }  # st:source type | pl:payload
    client.transmit( "cgp", pickle.dumps(tstMsg) )
