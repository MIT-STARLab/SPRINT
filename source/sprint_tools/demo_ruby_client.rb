require 'socket'
require 'openssl'

require 'json'

c_dir = Dir.getwd + '/../central_global_planner/certs/' # + c_dir
f_cert = c_dir+"client.cert"
f_key  = c_dir+"client.pkey"

socket = TCPSocket.open('localhost', 54202)
ssl_context = OpenSSL::SSL::SSLContext.new()
ssl_context.cert = OpenSSL::X509::Certificate.new(File.open(f_cert))
ssl_context.key = OpenSSL::PKey::RSA.new(File.open(f_key))
ssl_context.ssl_version = :SSLv23
ssl_socket = OpenSSL::SSL::SSLSocket.new(socket, ssl_context)
ssl_socket.sync_close = true
ssl_socket.connect


##### ----- User Defined: Define request to GP ----- #####
##### ----- Send downlinked state update from satellite, and requrest most recent plan for uplink ----- #####
##### ----- This can be triggered on receipt of satellite TT&C downlink, or user command ----- #####

##### ----- End User Defined ----- #####



###### ----- Core GS Functions ----- ######
data = {                        # Request most recent plan
    "req_type" => "reqPlan",
    "payload"  => nil           # None
}
# data = {
#     "req_type" => 'updateSat',
#     "payload"  => {
#         'satID'     => 'S0',    # etc
#         'sat_state' => {    # for each, a list of pairs; each pair is a time & state ; one entry shown for each
#             'power' => [   ["2016-02-14T04:00:00.000000Z",  {"DS_state" =>500000}] ],
#             'data'  => [   ["2016-02-14T04:00:00.000000Z",  {"batt_e_Wh"=>12}]     ],
#             'orbit' => [   ["2016-02-14T04:00:00.000000Z",  {
#                                                                 "a_km"        => 7378,
#                                                                 "e"           => 0,
#                                                                 "i_deg"       => 97.86,
#                                                                 "RAAN_deg"    => 0,
#                                                                 "arg_per_deg" => 0,
#                                                                 "M_deg"       => 180
#                                                             }
#                             ]
#                         ]
#         }
#     }
# }

###### ----- Supporting GS Functions ----- ######

# data = {
#     "req_type" => 'regenPlan',  # Force regen of plan - should be automatically generated when GP ingests changes
#     "payload"  => [ nil ]       # nil for all live use when GP controls its own time. 
# }
###### Details on payloads for add & remove sat can be found in cgp_main.py
# data = {
#     "req_type" => 'addSat',
#     "payload"  => nil  
# }
# data = {
#     "req_type" => 'removeSat',
#     "payload"  => nil  
# }
# data = {                        # Signal the GP to exit.
#     "req_type" => "quit",
#     "payload"  => nil           # None
# }


msg = JSON.generate(data)

START_MARKER = "size:"

ssl_socket.puts START_MARKER+[msg.length].pack("L>")+msg # "'B'*50024"
all_data = []

while partial_data = ssl_socket.read(16)  #read # (3) #.rcv
  all_data << partial_data

  if partial_data=="ACK" # Log or act if response required
    break
  end

end

data = all_data.join().slice!(START_MARKER.length+4...)
data = JSON.parse(data)

# puts data

##### ----- User Defined: Select from 'data' to build next packet to sat node, as appropriate ----- #####

##### ----- End User Defined ----- #####


ssl_socket.close

