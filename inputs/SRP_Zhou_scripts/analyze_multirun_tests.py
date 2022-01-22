# this file is for generating plots / outputs from
# the json files in this folder
import json
import matplotlib.pyplot as plt
import numpy as np

SRP_settings = [True, False]
GS_disruptions = ['None','G0','G1','G2']

# grab all data
all_data = {}
for SRP_setting in SRP_settings:
    for GS_disruption in GS_disruptions:
        cur_str = 'SRP_Test_SRP_%s_GS_%s' % (SRP_setting, GS_disruption)

        with open('.\\multirun_tests\\' + cur_str + '.json', "r") as jsonFile:
            all_data[cur_str] = json.load(jsonFile)

print('All Data Loaded')

print('test time')
# initialize all data structs
total_failures = []

median_data_margin_prcnt = []
prcntl25_ave_d_margin_prcnt = []
prcntl75_ave_d_margin_prcnt = []

median_energy_margin_prcnt = []
prcntl25_ave_e_margin_prcnt = []
prcntl75_ave_e_margin_prcnt = []

exec_over_poss = []
total_exec_dv = []
total_poss_dv = []

median_obs_initial_lat_exec = [] # initial means the first part of the data container downlinked
prcntl25_obs_initial_lat_exec = []
prcntl75_obs_initial_lat_exec = []

median_av_aoi_exec = []
prcntl25_av_aoi_exec = []
prcntl75_av_aoi_exec = []

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
    for GS_disruption in GS_disruptions:
        cur_str = 'SRP_Test_BDT_False_SRP_%s_GS_%s' % (SRP_setting, GS_disruption)
        cur_data = all_data[cur_str]
        # Activity Failures
        total_failures[ind].append(sum(cur_data['Num Failures by Type'].values()))

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

def autolabel(rects,axis):
    """
    Attach a text label above each bar displaying its height
    from: https://matplotlib.org/examples/api/barchart_demo.html 
    """
    for rect in rects:
        height = rect.get_height()
        axis.text(rect.get_x() + rect.get_width()/4., height,
                '%d' % int(height),
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

# MAKE PLOTS
N = 4   # maybe change to 4 if we add nominal case
width = 0.35       # the width of the bars
xLabelStr = 'Ground Station Failures'
xTickLabels = ('None','G0 - 24 hrs', 'G1 - 12 hrs', 'G2 -24 hrs')
legendStrs = ('SRP On', 'SRP Off')

############# one plot for total failures ####################
fig, ax = plt.subplots()
yLabelStr = 'Total Activity Failures (#)'
titleStr = 'Activity Failures with SRP on/off'
double_bar_graph(ax,N,total_failures,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs)

###### one plot with two subplots (one for each state margin level) ######
fig, ax1 = plt.subplots(nrows=1, ncols=1)
yLabelStr = 'Data Margin (%)'
titleStr = 'Data Margin Levels with SRP on/off'
d_yerr = (np.asarray([prcntl25_ave_d_margin_prcnt[0],prcntl75_ave_d_margin_prcnt[0]]),np.asarray([prcntl25_ave_d_margin_prcnt[1],prcntl75_ave_d_margin_prcnt[1]]))
double_bar_graph(ax1,N,median_data_margin_prcnt,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=d_yerr)

""" yLabelStr = 'Energy Margin (%)'
titleStr = 'Energy Margin Levels with SRP on/off'
e_yerr = (np.asarray([prcntl25_ave_e_margin_prcnt[0],prcntl75_ave_e_margin_prcnt[0]]),np.asarray([prcntl25_ave_e_margin_prcnt[1],prcntl75_ave_e_margin_prcnt[1]]))
double_bar_graph(ax2,N,median_energy_margin_prcnt,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,yerr=e_yerr) """


###### one plot with a three subplots (one for each metric) ###
# Data Throughput Percentage
fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1)
#titleStr = 'Metrics with SRP on/off'
yLabelStr = 'Data Throughput - Exec / Poss (%)'
titleStr = 'DV Throughput with SRP on/off'
xLabelStr = ''
double_bar_graph(ax1,N,exec_over_poss,yLabelStr,titleStr,xLabelStr,xTickLabels,legendStrs,legendFlag = False)


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


