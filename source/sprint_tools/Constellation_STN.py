import json
import networkx as nx
import matplotlib.pyplot as plt
from sprint_tools.Sprint_Types import AgentType 

"""
Constellation_STN will track the network topologically, with embedded temporal info.

This object is built to manage the underlying STN which describes the 
domain over which planning and replanning takes place.  It will provide
concise access to these details, searchability, and fracturability such that"
subgraphs can be appropriately spun off of it.  It will provide time evolution
functionality.

"""

class Constellation_STN:
    """
    Constellation_STN.from_orbit_prop_data_file

    This classmethod-style constructor ingests a file of the format given by
    orbit_prop_data.json, the output of the orbit propagator.
    :param self      The object pointer.
    :param file_name Name of the file where the access data is generated

    """

    @classmethod
    def from_orbit_prop_data_file(cls, file_name):
        orbit_prop_data_FILENAME = file_name
        with open(orbit_prop_data_FILENAME,'r') as f:
            opd = json.load(f)
        return cls(opd)


    #

    def __init__(self, stn_params):
        """
        Takes the datablob expected in the orbit_prop_data file.  Good for when
        the sim startup loads the file ahead of time.  To be superceded by
        a bare constructor.
        :param self              The object pointer.
        :param orbit_prop_data   Blob of orbit_prop_data.json file
        :param stn_params:
        """
        self.graph = nx.Graph()

        # All of these structures: 
            # For all sats 1-N in ID order:
                # For all targets, 1-T, in ID order:
                    # List of Accesses, chron ordered
                        # star/stop/duration per access
        all_xlnk_accesses_from_all_sats = stn_params['accesses_data']['xlnk_times']
        all_dlnk_accesses_from_all_sats = stn_params['accesses_data']['dlnk_times']
        all_obs_accesses_from_all_sats  = stn_params['accesses_data']['obs_times']

        sat_id_by_indx     = stn_params['element_id_by_index']['sat_id_by_indx']
        gs_id_by_indx      = stn_params['element_id_by_index']['gs_id_by_indx']
        trget_id_by_indx   = stn_params['element_id_by_index']['trget_id_by_indx']

        # The count in this shall be a proxy for number and ID-order of 
        # satellites, and reused in the subsequent listing retrievals

        #  Add all elements to graph to establish types ahead of use
        for sat_ID in sat_id_by_indx:
            self.graph.add_node(sat_ID, **{'type':AgentType.SAT}) 
        for gs_ID in gs_id_by_indx:
            self.graph.add_node(gs_ID,  **{'type':AgentType.GS})  
        for targ_ID in trget_id_by_indx:
            self.graph.add_node(targ_ID,**{'type':'targ'})


        ##### Cycle over satellites to gather access of all types #####
        for u in range(0, len(all_xlnk_accesses_from_all_sats)):
            satID_u = sat_id_by_indx[u] 

            ##### Cycle over _other_ satellite XLNKs underneath said sat ^ #####
            all_xlnk_access_from_a_sat = all_xlnk_accesses_from_all_sats[u]
            v=0
            for all_accesses_per_sat_pair in all_xlnk_access_from_a_sat:    # For all sats from a particular sat
                satID_v = sat_id_by_indx[v] 
                for access in all_accesses_per_sat_pair:    # For each actual window.
                    # TODO - make this block a function as it is so repeated;
                            # But, it's for a feature (json) that we're moving
                            # away from, so deprioritized
                    if(len(access)==3):                     # if non-empty
                        # Taking the first two terms of an access here; dropping the duration term
                        if self.graph.has_edge(satID_u,satID_v): # POLICY: Don't Add an edge if no windows
                            self.graph.add_edge(
                                satID_u,satID_v,
                                **{ 'windows': sorted(
                                        [*self.graph[satID_u][satID_v]['windows'], (access[0],access[1])],
                                        key=lambda tup: tup[1]),
                                    'type':'xlnk'  # TODO - Optimize by not resorting sorting each time
                                }  
                            )
                        else:
                            self.graph.add_edge(satID_u,satID_v,**{'windows':[(access[0],access[1])],'type':'xlnk'})
                v+=1

            ##### Cycle over _DOWNLINKs_ under said sat ^ #####
            all_dlnk_accesses_from_a_sat = all_dlnk_accesses_from_all_sats[u]
            g=0
            for all_accesses_per_satGS_pair in all_dlnk_accesses_from_a_sat:    # For all obs from a particular sat
                gsID_v = gs_id_by_indx[g]
                for access in all_accesses_per_satGS_pair:  # For each actual window.
                    if(len(access)==3):                     # if non-empty
                        # Taking the first two terms of an access here; dropping the duration term
                        if self.graph.has_edge(satID_u,gsID_v): # POLICY: Don't Add an edge if no windows
                            self.graph.add_edge(
                                satID_u,gsID_v,
                                **{ 'windows': sorted(
                                        [*self.graph[satID_u][gsID_v]['windows'], (access[0],access[1])],
                                        key=lambda tup: tup[1]),  # TODO - Optimize by not resorting sorting each time
                                    'type':'dlnk'
                                }  
                            )
                        else:
                            self.graph.add_edge(satID_u,gsID_v,**{'windows':[(access[0],access[1])],'type':'dlnk'})
                g+=1

            

            ##### Cycle over _OBSERVATIONS_ under said sat ^ #####
            all_obs_accesses_from_a_sat = all_obs_accesses_from_all_sats[u]
            o=0
            for all_accesses_per_satobs_pair in all_obs_accesses_from_a_sat:    # For all obs from a particular sat
                obsID_v = trget_id_by_indx[o]
                for access in all_accesses_per_satobs_pair: # For each actual window.
                    if(len(access)==3):                     # if non-empty
                        # Taking the first two terms of an access here; dropping the duration term
                        if self.graph.has_edge(satID_u,obsID_v): # POLICY: Don't Add an edge if no windows
                            self.graph.add_edge(
                                satID_u,obsID_v,
                                **{ 'windows': sorted(
                                        [*self.graph[satID_u][obsID_v]['windows'], (access[0],access[1])],
                                        key=lambda tup: tup[1]),  # TODO - Optimize by not resorting sorting each time
                                    'type':'obs'
                                }  
                            )
                        else:
                            self.graph.add_edge(satID_u,obsID_v,**{'windows':[(access[0],access[1])],'type':'obs'})
                o+=1



    def show(self):
        """
        Show Constellation_STN

        Provides a quick and dirty visualizer. Not suitable for large networks.
        Only shows overall topology, not temporal features.
        :param self      The object pointer to the Constellation_STN.

        """
        color_map = []
        for node in self.graph:
            if node['type'] == AgentType.SAT:
                color_map.append('red')
            elif node['type'] == AgentType.GS:
                color_map.append('orange')
            elif node['type'] == 'targ':
                color_map.append('xkcd:azure')

        nx.draw_circular(self.graph, node_color = color_map, with_labels = True)
        plt.show()


    def check_linkwindow_valid(self, edge, time):
        """
        Window Checker
        private: Abstracted as such to allow us to change how we validate the window
        :param edge: edge under consideration (carries windows in it)
        :param time: time to check - type dictated by constructor; mjd float, based in input format
        """
        for w in edge[2]['windows']:  # If we guarentee the windows are in order, could cut this iteration off sooner
            if time > w[0] and time < w[1]:
                return True
        return False

    def check_groundlink_available(self, node_ID, time):
        """
        Check if a link to/from ground is available.
        NOTE: Deprecated, use Constellation_STN::get_graph_neighbors()  (or at least CALL it)

        :param node_ID: The node (a sat) we want to confirm can reach a GS
        :param time: The time when we want to check if the time exists - type dictated by constructor; mjd float,
                     based in input format
        :return:     Returns an empty list if none available
        """
        downlinks = [e for e in self.graph.edges(node_ID,data=True) if (self.graph.nodes[e[1]]['type'] == AgentType.GS) ]  # Filter link windows over those including the node of interest, and paired with a GS
        accessable_GS = []   
        i = 0
        for e in downlinks:
            if self.check_linkwindow_valid(e, time):
                accessable_GS.append(downlinks[i][1])
            i+=1
        return accessable_GS

    def check_access_available(self, node_1_ID, node_2_ID, time):
        """
        Check if a particular link between two nodes is valid

        For a particular node and time, checks if an access to any GS exists.

        :param node_1_ID:  a particular node (sat or GS or obs)
        :param node_2_ID:  another particular node (sat or GS or obs)
        :param time:       The time when we want to check if the time exists - type dictated by constructor; mjd float,
                           based in input format
        :return:
        """
        accesses = [e for e in self.graph.edges(node_1_ID,data=True) if (e[1] == node_2_ID)]  # Filter link windows over those including the node of interest, and paired with a GS
        assert(len(accesses) <= 1) # Looking for a particular link, should be singular at most, or graph built wrong
        if(len(accesses) == 0):
            return False
        else:
            return self.check_linkwindow_valid(accesses[0], time)

    def get_sats_with_cur_access_to(self, agent_ID, time, check_satlist=None):  # TODO, add some negative version of the check that we can avoid
        """
        Get all the sats with a valid current window for this groundstation; can limit it to a list if provided
        # NOTE: Deprecated, use Constellation_STN::get_graph_neighbors()

        :param agent_ID: ID of the groundstation or sat of interest
        :param time:
        :param check_satlist: list of SatID's to limit the search to
        :return:
        """
        if check_satlist is None: # just get all current accesses for this GS
            accessable_sats = (e[1] for e in self.graph.edges(agent_ID,data=True) if self.check_linkwindow_valid(e, time) ) # Access for this GS that are currently valid
        else:
            accessable_sats = (e[1] for e in self.graph.edges(agent_ID,data=True) if (self.check_linkwindow_valid(e, time) and (e[1] in check_satlist) ) )  # But limited to the list;  TODO - if this list itir blows up, optimize
        return accessable_sats

    def get_graph_neighbors(self, agent_ID, time=None, neigh_type=None, guest_list=None):
        """
        Get all the agents with line-of-sight access to neighbors, with optional filters

        :param agent_ID:    ID of the groundstation or sat of interest
        :param time:        If time provided, only return neighbors whose corresponding access link window (edge) is
                            active
        :param neigh_type:  If type provided, only return neighbors who match that type
        :param guest_list:  If list provided, only return neighbors exist on the list
                            TODO - what use case shouldn't this filter be in the caller's flow?
        :return:
        """

        # TODO - when get_sats_with_cur_access_to is fully replaced by get_graph_neighbors,
        #  replace the object check_linkwindow_valid implementation with this.
        def check_access_active(edge_data, time):
            for w in edge_data['windows']:  
                if time > w[0] and time < w[1]:
                    return True
            return False

        def disqualify(neigh_id):   # Filters
            if   (neigh_type is not None) and (self.graph.nodes[neigh_id]['type'] != neigh_type):
                return True
            elif (guest_list is not None) and (neigh_id not in guest_list):
                return True
            elif (time is not None) and (not check_access_active(self.graph.get_edge_data(agent_ID, neigh_id), time) ):
                return True    # Last, b/c slowish
            else:
                return False     # not caught by any filters, carry on

        ret = list((x for x in nx.all_neighbors(self.graph,agent_ID) if not disqualify(x)))

        return ret


    ##### NOT YET IMPLEMENTED #####
    # def __init__(self):                       # Init empty, also need functions to populate programatically
    # def getLocal_STN(node, kneighborhood_size):   # Get a subset around a node
    # def shed_past_windows(cur_time):          # Maybe track a "next" window to shed, 
                                                # and have this return the next 
                                                # expected one (to avoid polling this)



