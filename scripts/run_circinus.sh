#! /bin/bash

# dir_opt=1day
dir_opt=4hour
# scen_name=sso10sat
scen_name=walker100_inc60
# dir_opt_params=polar_gs_targs3/dlnk_and_xlnk
dir_opt_params=polar_gs_targs3/dlnk_and_xlnk

run_orbit_prop="false"



#  note that this history input option technically defaults to "sat_link_only" 
#  if no argument is explicitly provided to OrbitViz.  including here for clarity though
history_input_option=sat_link_only

# prop_inputs=orbit_prop_inputs_ex.json
prop_data=orbit_prop_data.json
data_rates=data_rates_output.json
sat_link=sat_link_history.json
cached_accesses=cached_xlnks_ecl.json
# use_cached="false"
use_cached="true"

prop_inputs=orbit_prop_inputs.json
link_inputs=orbit_link_inputs.json


ORBIT_PROP_PATH="../source/circinus_orbit_propagation"
ORBIT_LINK_PATH="../source/circinus_orbit_link"
ORBIT_VIZ_PATH="../source/circinus_orbit_viz"

gen_inp_dir="../inputs/$dir_opt/$scen_name"
opt_inp_dir="../inputs/$dir_opt/$scen_name/$dir_opt_params"
opt_inp_dir_python="../../inputs/$dir_opt/$scen_name/$dir_opt_params"


comp_inp_dir=crux/config/examples
prop_inputs_r=$comp_inp_dir/$prop_inputs
cached_accesses_r=$comp_inp_dir/$cached_accesses
link_inputs_r=$comp_inp_dir/$link_inputs
prop_data_r=$comp_inp_dir/$prop_data
data_rates_r=$comp_inp_dir/$data_rates
sat_link_r=$comp_inp_dir/$sat_link


echo  $inp_dir/$prop_inputs
echo  use_cached $use_cached
# echo  $inp_dir/$prop_data
# echo  $inp_dir/$sat_link

if [ $use_cached = "true" ]
then
    echo  "$gen_inp_dir"/$cached_accesses
    cp "$gen_inp_dir"/$cached_accesses $ORBIT_PROP_PATH/$comp_inp_dir
fi

# Copy files over from input directory. some of these will be overwritten later if we run other parts of the pipeline
echo "copy files from input directory, if they exist"
cp "$opt_inp_dir/$prop_inputs" $ORBIT_PROP_PATH/$comp_inp_dir
cp "$opt_inp_dir/$prop_inputs" $ORBIT_LINK_PATH/$comp_inp_dir
cp "$opt_inp_dir/$link_inputs" $ORBIT_LINK_PATH/$comp_inp_dir
cp "$opt_inp_dir/$prop_data" $ORBIT_LINK_PATH/$comp_inp_dir
cp "$opt_inp_dir/$prop_data" $ORBIT_VIZ_PATH/$comp_inp_dir
cp "$opt_inp_dir/$prop_inputs" $ORBIT_VIZ_PATH/$comp_inp_dir

if [ $run_orbit_prop = "true" ]
then
    pushd $ORBIT_PROP_PATH/python_runner/
    if [ $use_cached = "true" ]
    then
        echo "running circinus_orbit_propagation with cached xlnks/eclipses"
        python runner_orbitprop.py --prop_inputs_file $prop_inputs_r --cached_accesses $cached_accesses_r
    else
        echo "running circinus_orbit_propagation"
        python runner_orbitprop.py --prop_inputs_file $prop_inputs_r
    fi
    popd
    cp $ORBIT_PROP_PATH/python_runner/orbit_prop_data.json $ORBIT_LINK_PATH/$comp_inp_dir
    cp $ORBIT_PROP_PATH/python_runner/orbit_prop_data.json $ORBIT_VIZ_PATH/$comp_inp_dir
fi


pushd $ORBIT_LINK_PATH/python_runner/
# python -m ipdb -c continue runner_orbitlink.py --prop_inputs_file $prop_inputs_r --link_inputs_file $link_inputs_r
python runner_orbitlink.py --prop_inputs_file $prop_inputs_r --link_inputs_file $link_inputs_r
popd
cp ./$ORBIT_LINK_PATH/python_runner/sat_link_history.json $ORBIT_VIZ_PATH/$comp_inp_dir


pushd $ORBIT_VIZ_PATH/python_runner/
python runner_orbitviz.py --prop_inputs_file "$prop_inputs_r" --prop_data_file "$prop_data_r" --sat_link_file "$sat_link_r" --history_input_option  $history_input_option
popd

pushd /tmp
DATE=`date '+%Y-%m-%d_%H-%M-%S'`
mkdir circinus_$DATE
popd
cp $ORBIT_PROP_PATH/python_runner/orbit_prop_data.json /tmp/circinus_$DATE
cp ./$ORBIT_LINK_PATH/python_runner/sat_link_history.json /tmp/circinus_$DATE
cp ./$ORBIT_LINK_PATH/python_runner/data_rates_output.json /tmp/circinus_$DATE
cp  $ORBIT_PROP_PATH/$prop_inputs_r /tmp/circinus_$DATE
