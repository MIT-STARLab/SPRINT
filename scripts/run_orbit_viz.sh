#! /bin/bash

# dir_opt=4hour
dir_opt=1day
# scen_name=sso10sat
# scen_name=walker18_inc30
scen_name=walker30_inc30
# scen_name=walker60_inc60
# scen_name=zhou2017_comparison
# scen_name=walker100_inc60
# scen_name=walker28_4orb_inc30
# dir_opt_params=polar_gs_targs3/dlnk_and_xlnk
# dir_opt_params=17gs_targs3/dlnk_and_xlnk
dir_opt_params=17gs_targs3/dlnk_and_xlnk
# dir_opt_params=7gs_targs3/dlnk_and_xlnk
# dir_opt_params=dlnk_and_xlnk





history_input_option=sat_link_only
# history_input_option=gp_and_sat_link
display_link_info="false"
# display_link_info="true"

prop_inputs=orbit_prop_inputs.json
data_rates=data_rates_output.json
prop_data=orbit_prop_data.json
gp_outputs=gp_outputs.json
sat_link=sat_link_history.json

# this is relative to THIS file
ORBIT_VIZ_PATH="../source/circinus_orbit_viz"

# this is relative to each repo base in CIRCINUS/source/
gen_inp_dir_python="../../inputs/$dir_opt/$scen_name"
opt_inp_dir_python="../../inputs/$dir_opt/$scen_name/$dir_opt_params"
opt_inp_dir="../inputs/$dir_opt/$scen_name/$dir_opt_params"


prop_inputs_r=$opt_inp_dir_python/$prop_inputs
data_rates_r=$opt_inp_dir_python/$data_rates
prop_data_r=$opt_inp_dir_python/$prop_data
sat_link_r=$opt_inp_dir_python/$sat_link


if [ $display_link_info = "true" ]
then
    display_link_info=--display_link_info
else
    display_link_info=
fi

# copy this, because orbit viz assumes a fixed location
comp_inp_dir=crux/config/examples
cp "$opt_inp_dir/$gp_outputs" $ORBIT_VIZ_PATH/$comp_inp_dir

echo  $prop_inputs
echo  $prop_data
echo  $sat_link
echo  $display_link_info

pushd $ORBIT_VIZ_PATH/python_runner/
python runner_orbitviz.py --prop_inputs_file "$prop_inputs_r" --prop_data_file "$prop_data_r" --sat_link_file "$sat_link_r" --history_input_option  $history_input_option $display_link_info
# python -m ipdb -c continue runner_orbitviz.py --prop_inputs_file "$prop_inputs_r" --prop_data_file "$prop_data_r" --sat_link_file "$sat_link_r" --history_input_option  $history_input_option $display_link_info
popd