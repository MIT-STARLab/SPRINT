# this file is for generating plots / outputs from
# the json files in this folder
import json
import matplotlib.pyplot as plt
import numpy as np

SRP_settings = [True, False]

n_targs = 15
total_targs = 100
num_sats = 30
#targ_subsets = [list(range(40,60)),list(range(0,total_targs,int(total_targs/n_targs)))] # first is all equatorial set, 2nd is spread out at all latitudes
targ_subsets = [list(range(40,60))]
#GS_subsets = [[3,5,6,14],[13,14,15,3,4,5,6,8,12]]
GS_subsets = [[3,5,6,14]]
plot_nominal = False
plot_disruption_case = not plot_nominal
average_across_targets = False


# grab all data
all_data = {}
if plot_disruption_case:
    # SELECT USE CASE to plot
    g_select = 0
    t_select = 0
    # LOAD DISRUPTED DATA SET
    for g_setting_ind,GS_subset in enumerate(GS_subsets):
        for t_setting_ind, t_subset in enumerate(targ_subsets):
            setting_name = 'setGS_%d_setT_%d' % (g_setting_ind,t_setting_ind)
            for SRP_setting in SRP_settings:

                GS_disruptions = [
                    "G%d" % GS_subset[0],
                    "G%d" % GS_subset[1],
                    "G%d" % GS_subset[2]
                    ]
                for GS_disruption in GS_disruptions:
                    scenario_name = 'WALKER_%d_SRP_Test_SRP_%s_GS_%s_%s' % (num_sats,SRP_setting, GS_disruption,setting_name)

                    with open('.\\multirun_tests\\' + scenario_name + '.json', "r") as jsonFile:
                        all_data[scenario_name] = json.load(jsonFile)

                    if g_setting_ind == g_select and t_setting_ind == t_select:
                        plot_disruption_str = setting_name
                        plot_GS_disruptions = GS_disruptions

if plot_nominal:
    # LOAD NOMINAL DATA
    nominal_names = []
    nominal_names_full = []
    for g_setting_ind,GS_subset in enumerate(GS_subsets):
        for t_setting_ind, t_subset in enumerate(targ_subsets):
            setting_name = 'setGS_%d_setT_%d' % (g_setting_ind,t_setting_ind)
            scenario_name = 'WALKER_%d_Nominal_%s' % (num_sats,setting_name)
            nominal_names.append('G%d_T%d' % (g_setting_ind,t_setting_ind))
            nominal_names_full.append(scenario_name)
            with open('.\\multirun_tests\\' + scenario_name + '.json', "r") as jsonFile:
                all_data[scenario_name] = json.load(jsonFile)

print('All Data Loaded')

# helper functions
def autolabel(rects,axis):
        """
        Attach a text label above each bar displaying its height
        from: https://matplotlib.org/examples/api/barchart_demo.html 
        """
        for rect in rects:
            height = rect.get_height()
            axis.text(rect.get_x() + rect.get_width()/2.5, height,
                    '%.2f' % height,
                    ha='center', va='bottom')

def double_bar_graph(ax,N,data,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr = [None, None], legendFlag = True, colorStrs = ['b','gray'],width=0.35,):

    if len(data) != 2:
        raise Exception('Need exactly 2 data sets')

    if N != len(data[0]) or N != len(data[1]) or N != len(xTickLabels):
        raise Exception('number of bar graphs does not match data and/or tick labels supplied')

    ind = np.arange(N)  # the x locations for the groups

    rects1 = ax.bar(ind, data[0], width, color=colorStrs[0], yerr= yerr[0])
    rects2 = ax.bar(ind + width, data[1], width, color=colorStrs[1], yerr= yerr[1])
    ax.set_ylabel(yLabelStr)
    ax.set_title(titleStr)
    ax.set_xticks(ind + width / 2)
    ax.set_xlabel(xLabelStr)
    ax.set_xticklabels(tuple(xTickLabels))
    if legendFlag:
        ax.legend((rects1[0], rects2[0]), tuple(legendStrs))
    autolabel(rects1,ax)
    autolabel(rects2,ax)

    return ax

def single_bar_graph(ax,N,data,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr = None, legendFlag = True, colorStrs = 'b',width=0.35,):


    if N != len(data) or N != len(xTickLabels):
        raise Exception('number of bar graphs does not match data and/or tick labels supplied')

    ind = np.arange(N)  # the x locations for the groups

    rects1 = ax.bar(ind, data, width, color=colorStrs, yerr= yerr)
    ax.set_ylabel(yLabelStr)
    ax.set_title(titleStr)
    ax.set_xticks(ind + width / 2)
    ax.set_xlabel(xLabelStr)
    ax.set_xticklabels(tuple(xTickLabels))
    if legendFlag:
        ax.legend((rects1), tuple(legendStrs))
    autolabel(rects1,ax)

    return ax

# initialize all data structs
total_failures = []
per_failures_xlnk = []
per_failures_dlnk = []


median_data_margin_prcnt = []
prcntl25_ave_d_margin_prcnt = []
prcntl75_ave_d_margin_prcnt = []

median_energy_margin_prcnt = []
prcntl25_ave_e_margin_prcnt = []
prcntl75_ave_e_margin_prcnt = []

exec_over_poss = []
exec_dv_GB = []
poss_dv_GB= []

median_obs_initial_lat_exec = [] # initial means the first part of the data container downlinked
prcntl25_obs_initial_lat_exec = []
prcntl75_obs_initial_lat_exec = []

median_av_aoi_exec = []
prcntl25_av_aoi_exec = []
prcntl75_av_aoi_exec = []

# PLOTS FOR NOMINAL CASE
if plot_nominal:
    for ind,scenario_name in enumerate(nominal_names_full):
        """ per_failures_xlnk.append([])
        per_failures_dlnk.append([])
        median_data_margin_prcnt.append([])
        prcntl25_ave_d_margin_prcnt.append([])
        prcntl75_ave_d_margin_prcnt.append([])
        median_energy_margin_prcnt.append([])
        prcntl25_ave_e_margin_prcnt.append([])
        prcntl75_ave_e_margin_prcnt.append([])
        exec_over_poss.append([])
        median_obs_initial_lat_exec.append([])
        prcntl25_obs_initial_lat_exec.append([])
        prcntl75_obs_initial_lat_exec.append([])
        median_av_aoi_exec.append([])
        prcntl25_av_aoi_exec.append([])
        prcntl75_av_aoi_exec.append([]) """

        cur_data = all_data[scenario_name]

        # Activity Failures
        per_failures_xlnk.append(cur_data['Percentage of Exec Act Failures by Act']['xlnk'])
        per_failures_dlnk.append(cur_data['Percentage of Exec Act Failures by Act']['dlnk'])

        # Data Margin levels
        median_data_margin_prcnt.append(cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt'])
        prcntl25_ave_d_margin_prcnt.append(cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt'] - cur_data['d_rsrc_stats']['prcntl25_ave_d_margin_prcnt'])
        prcntl75_ave_d_margin_prcnt.append(cur_data['d_rsrc_stats']['prcntl75_ave_d_margin_prcnt'] - cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt'])

        # Energy Margin levels
        median_energy_margin_prcnt.append(cur_data['e_rsrc_stats']['median_ave_e_margin_prcnt'])
        prcntl25_ave_e_margin_prcnt.append(cur_data['e_rsrc_stats']['median_ave_e_margin_prcnt']-cur_data['e_rsrc_stats']['prcntl25_ave_e_margin_prcnt'])
        prcntl75_ave_e_margin_prcnt .append(cur_data['e_rsrc_stats']['prcntl75_ave_e_margin_prcnt']-cur_data['e_rsrc_stats']['median_ave_e_margin_prcnt'])

        # METRICS
        # DV % throughput
        exec_over_poss.append(cur_data['dv_stats']['exec_over_poss']*100)
        exec_dv_GB.append(cur_data['dv_stats']['total_exec_dv']/1000)
        poss_dv_GB.append(cur_data['dv_stats']['total_poss_dv']/1000)

        # Obs Latency 
        median_obs_initial_lat_exec.append(cur_data['lat_stats']['median_obs_initial_lat_exec'])
        prcntl25_obs_initial_lat_exec.append(cur_data['lat_stats']['median_obs_initial_lat_exec'] - cur_data['lat_stats']['prcntl25_obs_initial_lat_exec'])
        prcntl75_obs_initial_lat_exec.append(cur_data['lat_stats']['prcntl75_obs_initial_lat_exec'] - cur_data['lat_stats']['median_obs_initial_lat_exec'])

        # AoI
        median_av_aoi_exec.append(cur_data['obs_aoi_stats_w_routing']['median_av_aoi_exec'])
        prcntl25_av_aoi_exec.append(cur_data['obs_aoi_stats_w_routing']['median_av_aoi_exec'] - cur_data['obs_aoi_stats_w_routing']['prcntl25_av_aoi_exec'])
        prcntl75_av_aoi_exec.append(cur_data['obs_aoi_stats_w_routing']['prcntl75_av_aoi_exec'] - cur_data['obs_aoi_stats_w_routing']['median_av_aoi_exec'])

    # MAKE PLOTS
    N = 1   # maybe change to 4 if we add nominal case
    width = 0.35       # the width of the bars
    xLabelStr = 'Nominal Case ID'
    titleMiniStr = 'in %d Sat Walker Nominal Cases' % num_sats
    xTickLabels = tuple(nominal_names)

    ############# one plot for total failures ####################
    fig, ax = plt.subplots()
    yLabelStr = 'Percentage Activity Failures (%)'
    titleStr = 'Percentage Activity Failures ' + titleMiniStr
    legendStrs = ('Xlnks', 'Dlnks')
    #percentage_failures = np.concatenate((np.asarray(per_failures_xlnk),np.asarray(per_failures_dlnk)),axis = 1)
    percentage_failures = [per_failures_xlnk, per_failures_dlnk]
    double_bar_graph(ax,N,percentage_failures,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,colorStrs = ['g','b'])

    ###### one plot with two subplots (one for each state margin level) ######
    fig, ax1 = plt.subplots(nrows=1, ncols=1)
    yLabelStr = 'Data Margin (%)'
    titleStr = 'Data Margin Levels '+ titleMiniStr
    d_yerr = (np.asarray([prcntl25_ave_d_margin_prcnt,prcntl75_ave_d_margin_prcnt]))
    single_bar_graph(ax1,N,median_data_margin_prcnt,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=d_yerr,legendFlag = False)

    ###### one plot with a three subplots (one for each metric) ###
    # Data Throughput Percentage
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1)
    #titleStr = 'Metrics with SRP on/off'
    yLabelStr = 'Data Throughput - Exec & Poss (GB)'
    titleStr = 'DV Throughput '+ titleMiniStr
    xLabelStr = ''
    legendStrs = ('Exec (GB)', 'Poss (GB)')
    exec_and_poss = [exec_dv_GB, poss_dv_GB]
    double_bar_graph(ax1,N,exec_and_poss,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs)


    xLabelStr = 'Nominal Case Id'
    # Median Latency
    yLabelStr = 'Observation Latency (min)'
    titleStr = 'Observation Initial Data Packet Latency '+ titleMiniStr
    lat_yerr = (np.asarray([prcntl25_obs_initial_lat_exec,prcntl75_obs_initial_lat_exec]))
    single_bar_graph(ax2,N,median_obs_initial_lat_exec,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=lat_yerr,legendFlag = False)

    """ # Median AoI
    yLabelStr = 'Age of Information (hours)'
    #titleStr = 'Observation Initial Data Packet Latency with SRP on/off'
    aoi_yerr = (np.asarray([prcntl25_av_aoi_exec[0],prcntl75_av_aoi_exec[0]]),np.asarray([prcntl25_av_aoi_exec[1],prcntl75_av_aoi_exec[1]]))
    double_bar_graph(ax3,N,median_av_aoi_exec,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=aoi_yerr) """
    ### SHOW PLOTS ###
    plt.show()

if plot_disruption_case:
    # MAKE DATA STRUCTS FOR BAR CHARTS
    for ind,SRP_setting in enumerate(SRP_settings):
        total_failures.append([])
        median_data_margin_prcnt.append([])
        prcntl25_ave_d_margin_prcnt.append([])
        prcntl75_ave_d_margin_prcnt.append([])
        median_energy_margin_prcnt.append([])
        prcntl25_ave_e_margin_prcnt.append([])
        prcntl75_ave_e_margin_prcnt.append([])
        exec_over_poss.append([])
        median_obs_initial_lat_exec.append([])
        prcntl25_obs_initial_lat_exec.append([])
        prcntl75_obs_initial_lat_exec.append([])
        median_av_aoi_exec.append([])
        prcntl25_av_aoi_exec.append([])
        prcntl75_av_aoi_exec.append([])
        for GS_disruption in plot_GS_disruptions:
            if average_across_targets:
                total_failures_temp = 0
                median_data_margin_prcnt_temp = 0
                prcntl25_ave_d_margin_prcnt_temp = 0
                prcntl75_ave_d_margin_prcnt_temp = 0
                median_energy_margin_prcnt_temp = 0
                prcntl25_ave_e_margin_prcnt_temp = 0
                prcntl75_ave_e_margin_prcnt_temp = 0
                exec_over_poss_temp = 0
                median_obs_initial_lat_exec_temp = 0
                prcntl25_obs_initial_lat_exec_temp = 0
                prcntl75_obs_initial_lat_exec_temp = 0
                median_av_aoi_exec_temp = 0
                prcntl25_av_aoi_exec_temp = 0
                prcntl75_av_aoi_exec_temp = 0

                num_cases = 0
                for t_setting_ind, t_subset in enumerate(targ_subsets):
                    num_cases += 1
                    setting_name = 'setGS_%d_setT_%d' % (g_select,t_setting_ind)
                    cur_str = 'WALKER_%d_SRP_Test_SRP_%s_GS_%s_%s' % (num_sats,SRP_setting, GS_disruption,setting_name)
                    cur_data = all_data[cur_str]

                    total_failures_temp += sum(cur_data['Percentage of Exec Act Failures by Act'].values())/3
                    median_data_margin_prcnt_temp += cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt']
                    prcntl25_ave_d_margin_prcnt_temp += cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt'] - cur_data['d_rsrc_stats']['prcntl25_ave_d_margin_prcnt']
                    prcntl75_ave_d_margin_prcnt_temp += cur_data['d_rsrc_stats']['prcntl75_ave_d_margin_prcnt'] - cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt']

                    exec_over_poss_temp += cur_data['dv_stats']['exec_over_poss']*100
                    median_obs_initial_lat_exec_temp += cur_data['lat_stats']['median_obs_initial_lat_exec']
                    prcntl25_obs_initial_lat_exec_temp += cur_data['lat_stats']['median_obs_initial_lat_exec'] - cur_data['lat_stats']['prcntl25_obs_initial_lat_exec']
                    prcntl75_obs_initial_lat_exec_temp += cur_data['lat_stats']['prcntl75_obs_initial_lat_exec'] - cur_data['lat_stats']['median_obs_initial_lat_exec']

                total_failures[ind].append(total_failures_temp/num_cases)

                # Data Margin levels
                median_data_margin_prcnt[ind].append(median_data_margin_prcnt_temp/num_cases)
                prcntl25_ave_d_margin_prcnt[ind].append(prcntl25_ave_d_margin_prcnt_temp/num_cases)
                prcntl75_ave_d_margin_prcnt[ind].append(prcntl75_ave_d_margin_prcnt_temp/num_cases)

                # METRICS
                # DV % throughput
                exec_over_poss[ind].append(exec_over_poss_temp/num_cases)

                # Obs Latency 
                median_obs_initial_lat_exec[ind].append(median_obs_initial_lat_exec_temp/num_cases)
                prcntl25_obs_initial_lat_exec[ind].append(prcntl25_obs_initial_lat_exec_temp/num_cases)
                prcntl75_obs_initial_lat_exec[ind].append(prcntl75_ave_d_margin_prcnt_temp/num_cases)

            else:
                cur_str = 'WALKER_%d_SRP_Test_SRP_%s_GS_%s_%s' % (num_sats,SRP_setting, GS_disruption,plot_disruption_str)
                cur_data = all_data[cur_str]
                # Activity Failures
                total_failures[ind].append(sum(cur_data['Percentage of Exec Act Failures by Act'].values())/3)

                # Data Margin levels
                median_data_margin_prcnt[ind].append(cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt'])
                prcntl25_ave_d_margin_prcnt[ind].append(cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt'] - cur_data['d_rsrc_stats']['prcntl25_ave_d_margin_prcnt'])
                prcntl75_ave_d_margin_prcnt[ind].append(cur_data['d_rsrc_stats']['prcntl75_ave_d_margin_prcnt'] - cur_data['d_rsrc_stats']['median_ave_d_margin_prcnt'])

                # Energy Margin levels
                median_energy_margin_prcnt[ind].append(cur_data['e_rsrc_stats']['median_ave_e_margin_prcnt'])
                prcntl25_ave_e_margin_prcnt[ind].append(cur_data['e_rsrc_stats']['median_ave_e_margin_prcnt']-cur_data['e_rsrc_stats']['prcntl25_ave_e_margin_prcnt'])
                prcntl75_ave_e_margin_prcnt [ind].append(cur_data['e_rsrc_stats']['prcntl75_ave_e_margin_prcnt']-cur_data['e_rsrc_stats']['median_ave_e_margin_prcnt'])

                # METRICS
                # DV % throughput
                exec_over_poss[ind].append(cur_data['dv_stats']['exec_over_poss']*100)

                # Obs Latency 
                median_obs_initial_lat_exec[ind].append(cur_data['lat_stats']['median_obs_initial_lat_exec'])
                prcntl25_obs_initial_lat_exec[ind].append(cur_data['lat_stats']['median_obs_initial_lat_exec'] - cur_data['lat_stats']['prcntl25_obs_initial_lat_exec'])
                prcntl75_obs_initial_lat_exec[ind].append(cur_data['lat_stats']['prcntl75_obs_initial_lat_exec'] - cur_data['lat_stats']['median_obs_initial_lat_exec'])

                # AoI
                median_av_aoi_exec[ind].append(cur_data['obs_aoi_stats_w_routing']['median_av_aoi_exec'])
                prcntl25_av_aoi_exec[ind].append(cur_data['obs_aoi_stats_w_routing']['median_av_aoi_exec'] - cur_data['obs_aoi_stats_w_routing']['prcntl25_av_aoi_exec'])
                prcntl75_av_aoi_exec[ind].append(cur_data['obs_aoi_stats_w_routing']['prcntl75_av_aoi_exec'] - cur_data['obs_aoi_stats_w_routing']['median_av_aoi_exec'])

    # MAKE PLOTS
    N = 3   # maybe change to 4 if we add nominal case
    width = 0.35       # the width of the bars
    xLabelStr = 'Ground Station Failures'
    xTickLabels = tuple(plot_GS_disruptions)
    legendStrs = ('SRP On', 'SRP Off')

    ############# one plot for total failures ####################
    fig, ax = plt.subplots()
    yLabelStr = 'Average Activity Failures (%)'
    titleStr = 'Activity Failures % with SRP on/off'
    double_bar_graph(ax,N,total_failures,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs)

    ###### one plot with two subplots (one for each state margin level) ######
    fig, ax1 = plt.subplots(nrows=1, ncols=1)
    yLabelStr = 'Data Margin (%)'
    titleStr = 'Data Margin Levels with SRP on/off'
    d_yerr = (np.asarray([prcntl25_ave_d_margin_prcnt[0],prcntl75_ave_d_margin_prcnt[0]]),np.asarray([prcntl25_ave_d_margin_prcnt[1],prcntl75_ave_d_margin_prcnt[1]]))
    double_bar_graph(ax1,N,median_data_margin_prcnt,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=d_yerr)


    ###### one plot with a three subplots (one for each metric) ###
    # Data Throughput Percentage
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1)
    #titleStr = 'Metrics with SRP on/off'
    yLabelStr = 'Data Throughput - Exec / Poss (%)'
    titleStr = 'DV Throughput with SRP on/off'
    xLabelStr = ''
    double_bar_graph(ax1,N,exec_over_poss,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs)


    xLabelStr = 'Ground Station Failures'
    # Median Latency
    yLabelStr = 'Observation Latency (min)'
    titleStr = 'Observation Initial Data Packet Latency with SRP on/off'
    lat_yerr = (np.asarray([prcntl25_obs_initial_lat_exec[0],prcntl75_obs_initial_lat_exec[0]]),np.asarray([prcntl25_obs_initial_lat_exec[1],prcntl75_obs_initial_lat_exec[1]]))
    double_bar_graph(ax2,N,median_obs_initial_lat_exec,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=lat_yerr,legendFlag = False)

    """ # Median AoI
    yLabelStr = 'Age of Information (hours)'
    #titleStr = 'Observation Initial Data Packet Latency with SRP on/off'
    aoi_yerr = (np.asarray([prcntl25_av_aoi_exec[0],prcntl75_av_aoi_exec[0]]),np.asarray([prcntl25_av_aoi_exec[1],prcntl75_av_aoi_exec[1]]))
    double_bar_graph(ax3,N,median_av_aoi_exec,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=aoi_yerr) """
    ### SHOW PLOTS ###
    plt.show()


