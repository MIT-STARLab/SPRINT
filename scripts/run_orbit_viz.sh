#! /bin/bash

dir_opt=4hour
# dir_opt=1day
scen_name=sso10sat
scen_name=sso10sat
# scen_name=walker18_inc30
# scen_name=walker30_inc30
# scen_name=walker100_inc60
# dir_opt_params=polar_gs_targs3/dlnk_and_xlnk
# dir_opt_params=17gs_targs3/dlnk_and_xlnk
dir_opt_params=7gs_targs3/dlnk_and_xlnk






history_input_option=sat_link_only
# history_input_option='gp_and_sat_link'
display_link_info="false"
# display_link_info="true"

prop_inputs=orbit_prop_inputs.json
data_rates=data_rates_output.json
prop_data=orbit_prop_data.json
gp_outputs=gp_outputs.json
sat_link=sat_link_history.json


ORBIT_VIZ_PATH="../source/circinus_orbit_viz"

gen_inp_dir="../../inputs/$dir_opt/$scen_name"
opt_inp_dir="../../inputs/$dir_opt/$scen_name/$dir_opt_params"


prop_inputs_r=$opt_inp_dir/$prop_inputs
data_rates_r=$opt_inp_dir/$data_rates
prop_data_r=$opt_inp_dir/$prop_data
sat_link_r=$opt_inp_dir/$sat_link


if [ $display_link_info = "true" ]
then
    display_link_info=--display_link_info
else
    display_link_info=
fi


echo  $prop_inputs
echo  $prop_data
echo  $sat_link
echo  $display_link_info

pushd $ORBIT_VIZ_PATH/python_runner/
# python runner_orbitviz.py --prop_inputs_file "$prop_inputs_r" --prop_data_file "$prop_data_r" --sat_link_file "$sat_link_r" --history_input_option  $history_input_option $display_link_info
python -m ipdb -c continue runner_orbitviz.py --prop_inputs_file "$prop_inputs_r" --prop_data_file "$prop_data_r" --sat_link_file "$sat_link_r" --history_input_option  $history_input_option $display_link_info
popd