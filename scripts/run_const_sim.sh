#! /bin/bash


dir_opt=1day
scen_name=zhou2017_comparison
# scen_name=sso10sat
# scen_name=walker30_inc30
# dir_opt_params=polar_gs_targs3/dlnk_and_xlnk
# dir_opt_params=polar_gs_targs3/dlnk
dir_opt_params=dlnk_and_xlnk
# dir_opt_params=17gs_targs3/dlnk_and_xlnk
const_sim_params_inputs=const_sim_params_fullday.json


gp_general_inputs_opt=custom
const_sim_params_inputs_opt=custom


CIRCINUS_SIM_PATH="../source/circinus_sim"

# this is relative to each repo base in CIRCINUS/source/
gen_inp_dir_python="../../inputs/$dir_opt/$scen_name"
opt_inp_dir_python="../../inputs/$dir_opt/$scen_name/$dir_opt_params"


prop_inputs=orbit_prop_inputs.json
link_inputs=orbit_link_inputs.json
data_rates=data_rates_output.json
prop_data=orbit_prop_data.json
gp_outputs=gp_outputs.json
sat_link=sat_link_history.json    
gp_general_params_inputs=gp_general_params_inputs.json    

echo  $opt_inp_dir_python/$prop_inputs
echo  $opt_inp_dir_python/$link_inputs
echo  $opt_inp_dir_python/$data_rates
echo  $opt_inp_dir_python/$prop_data

# comp_inp_dir=crux/config/examples
prop_inputs_r=$opt_inp_dir_python/$prop_inputs
link_inputs_r=$opt_inp_dir_python/$link_inputs
data_rates_r=$opt_inp_dir_python/$data_rates
gp_general_inputs_r=$opt_inp_dir_python/$gp_general_params_inputs
const_sim_params_inputs_r=$opt_inp_dir_python/$const_sim_params_inputs
prop_data_r=$opt_inp_dir_python/$prop_data
sat_link_r=$opt_inp_dir_python/$sat_link


if [ $gp_general_inputs_opt = "custom" ]
then
    gp_general_inputs_arg1="--gp_general_inputs_file"
    gp_general_inputs_arg2="$gp_general_inputs_r"
else
    gp_general_inputs_arg1=
    gp_general_inputs_arg2=
fi

if [ $const_sim_params_inputs_opt = "custom" ]
then
    const_sim_params_inputs_arg1="--const_sim_params_file"
    const_sim_params_inputs_arg2="$const_sim_params_inputs_r"
else
    const_sim_params_inputs_arg1=
    const_sim_params_inputs_arg2=
fi


pushd  $CIRCINUS_SIM_PATH/python_runner/
echo "python runner_const_sim.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r" $gp_general_inputs_arg1 "$gp_general_inputs_arg2" $const_sim_params_inputs_arg1 "$const_sim_params_inputs_arg2""
python runner_const_sim.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r" $gp_general_inputs_arg1 "$gp_general_inputs_arg2" $const_sim_params_inputs_arg1 "$const_sim_params_inputs_arg2"
# python -m cProfile runner_const_sim.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r" $gp_general_inputs_arg1 "$gp_general_inputs_arg2" $const_sim_params_inputs_arg1 "$const_sim_params_inputs_arg2"
# python -m ipdb -c continue runner_const_sim.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r" $gp_general_inputs_arg1 "$gp_general_inputs_arg2" $const_sim_params_inputs_arg1 "$const_sim_params_inputs_arg2"

popd
