#! /bin/bash

# dir_opt=4hour
dir_opt=1day
scen_name=zhou2017_comparison
# scen_name=sso10sat
# scen_name=walker18_inc30
# scen_name=walker30_inc30
# scen_name=walker100_inc60
# scen_name=walker60_inc60
# dir_opt_params=polar_gs_targs3/dlnk_and_xlnk
# dir_opt_params=polar_gs_targs3/dlnk_and_xlnk_unidirectional
# dir_opt_params=7gs_targs3/dlnk_and_xlnk
# dir_opt_params=17gs_targs3/dlnk_and_xlnk
dir_opt_params=dlnk_and_xlnk

# pickle_choice=b
gp_inst_inputs=gp_instance_params_inputs_var.json

# pickle_choice=fast
# pickle_choice=opt
# pickle_choice=b

# dir_opt_params=

# rs_pickle_opt=step1
# rs_pickle_opt=step2
# rs_pickle_opt=as
rs_pickle_opt=none
gp_general_inputs_opt=custom


GLOBAL_PLANNER_PATH="../source/access_global_planner"

gen_inp_dir_python="../../inputs/$dir_opt/$scen_name"
opt_inp_dir_python="../../inputs/$dir_opt/$scen_name/$dir_opt_params"
opt_inp_dir="../inputs/$dir_opt/$scen_name/$dir_opt_params"


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
gp_inst_inputs_r=$opt_inp_dir_python/$gp_inst_inputs
rs_s1_pickle_r=$opt_inp_dir_python/rs_s1_$pickle_choice.pkl
rs_s2_pickle_r=$opt_inp_dir_python/rs_s2_$pickle_choice.pkl
as_pickle_r=$opt_inp_dir_python/as_$pickle_choice.pkl
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

if [ $rs_pickle_opt = "step1" ]
then
    rs_s1_pickle_arg1="--rs_s1_pickle"
    rs_s1_pickle_arg2="$rs_s1_pickle_r"
else
    rs_s1_pickle_arg1="--rs_s1_pickle"
    rs_s1_pickle_arg2=
fi

if [ $rs_pickle_opt = "step2" ]
then
    rs_s2_pickle_arg1="--rs_s2_pickle"
    rs_s2_pickle_arg2="$rs_s2_pickle_r"
else
    rs_s2_pickle_arg1="--rs_s2_pickle"
    rs_s2_pickle_arg2=
fi

if [ $rs_pickle_opt = "as" ]
then
    as_pickle_arg1="--as_pickle"
    as_pickle_arg2="$as_pickle_r"
else
    as_pickle_arg1="--as_pickle"
    as_pickle_arg2=
fi

pushd  $GLOBAL_PLANNER_PATH/python_runner/
echo "python runner_gp.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r" $gp_general_inputs_arg1 "$gp_general_inputs_arg2" --gp_inst_inputs_file "$gp_inst_inputs_r" $rs_s1_pickle_arg1 "$rs_s1_pickle_arg2" $rs_s2_pickle_arg1 "$rs_s2_pickle_arg2" $as_pickle_arg1 "$as_pickle_arg2""
python runner_gp.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r" $gp_general_inputs_arg1 "$gp_general_inputs_arg2" --gp_inst_inputs_file "$gp_inst_inputs_r" $rs_s1_pickle_arg1 "$rs_s1_pickle_arg2"  $rs_s2_pickle_arg1 "$rs_s2_pickle_arg2" $as_pickle_arg1 "$as_pickle_arg2"
# # python -m cProfile runner_gp.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r"  $rs_s1_pickle_arg $rs_s2_pickle_arg $as_pickle_arg
# python -m ipdb -c continue runner_gp.py --prop_inputs_file  "$prop_inputs_r"  --data_rates_file "$data_rates_r" --link_inputs_file "$link_inputs_r" $gp_general_inputs_arg1 "$gp_general_inputs_arg2" --gp_inst_inputs_file "$gp_inst_inputs_r" $rs_s1_pickle_arg1 "$rs_s1_pickle_arg2" $rs_s2_pickle_arg1 "$rs_s2_pickle_arg2" $as_pickle_arg1 "$as_pickle_arg2"

cp $gp_outputs "$opt_inp_dir"

popd
