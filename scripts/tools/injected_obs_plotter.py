#! /usr/bin/env python

##
# Python runner for orbit visualization pipeline
# @author Kit Kennedy
#
from datetime import datetime,timedelta
import json
import sys

# day_start = datetime(2016,2,14,4,0,0)
# day_end = datetime(2016,2,15,4,0,0)
# sats = ["sat0","sat1","sat2","sat3","sat4","sat5"]

day_start = datetime(2018,1,18,0,0,0)
day_end = datetime(2018,1,19,0,0,0)
# sats = ["sat0","sat1","sat2","sat3","sat4","sat5","sat6","sat7","sat8","sat9"]
# sats = ["sat0","sat1","sat2","sat3","sat4","sat5","sat6","sat7","sat8","sat9","sat10","sat11","sat12","sat13","sat14"]
sats = ["sat15","sat16","sat17","sat18","sat19","sat20","sat21","sat22","sat23","sat24","sat25","sat26","sat27","sat28","sat29"]
# sats = ["sat0","sat1","sat2","sat3","sat4","sat5","sat6","sat7","sat8","sat9","sat10","sat11","sat12","sat13","sat14","sat15","sat16","sat17","sat18","sat19","sat20","sat21","sat22","sat23","sat24","sat25","sat26","sat27","sat28","sat29"]



sys.path.append ('../../source/circinus_sim')
from circinus_tools.plotting import plot_tools as pltl
from circinus_tools.scheduling.custom_window import   ObsWindow
from circinus_tools import time_tools as tt

with open('injects_walker30_inc30.json','r') as f:
    the_json = json.load(f)


all_obs = [[] for i in range(len(sats))]

for injected in the_json:
    if not injected['sat_id'] in sats:
        continue

    windid = injected['indx']
    sat_indx = sats.index(injected['sat_id'])
    start = tt.iso_string_to_dt(injected['start_utc'])
    end = tt.iso_string_to_dt(injected['end_utc'])
    obs = ObsWindow(windid, sat_indx, ['blah'], 0, start, end, wind_obj_type='injected')
    all_obs[sat_indx].append(obs)


plot_params = {}
plot_params['route_ids_by_wind'] = None
plot_params['plot_start_dt'] = day_start
plot_params['plot_end_dt'] = day_end
plot_params['base_time_dt'] = day_start

plot_params['plot_title'] = 'Injected Observations'
plot_params['y_label'] = 'Satellite Index'
plot_params['plot_size_inches'] = (18,9)
plot_params['plot_original_times_choices'] = False
plot_params['plot_executed_times_regular'] = True
plot_params['show'] = False
plot_params['fig_name'] = 'injected_obs.pdf'
plot_params['plot_fig_extension'] = 'pdf'

plot_params['time_units'] = 'hours'
plot_params['agent_id_order'] = sats

plot_params['plot_xlnks_choices'] = False
plot_params['plot_dlnks_choices'] = False
plot_params['plot_obs_choices'] = False
plot_params['plot_xlnks'] = False
plot_params['plot_dlnks'] = False
plot_params['plot_obs'] = True
plot_params['plot_include_obs_labels'] = True
plot_params['plot_include_xlnk_labels'] = False
plot_params['plot_include_dlnk_labels'] = False

plot_params['obs_choices_legend_name'] = ""
plot_params['obs_exe_legend_name'] =  "O inject"
plot_params['dlnk_choices_legend_name'] = ""
plot_params['dlnk_exe_legend_name'] = ""
plot_params['xlnk_choices_legend_name'] = ""
plot_params['xlnk_exe_legend_name'] = ""

plot_params['label_fontsize'] =  "12"


def obs_label_getter(obs):
    # return "o%d, dv %d/%d (%d)"%(obs.window_ID,obs.executed_data_vol,obs.executable_data_vol,obs.data_vol)
    return "o%d"%(obs.window_ID)
plot_params['obs_label_getter_func'] = obs_label_getter

pltl.plot_all_agents_acts(
    sats,
    [],
    all_obs,
    [],
    [], 
    [],
    [],
    plot_params)


