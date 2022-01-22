#! /bin/bash
printf "running: $0\n"

# # ---- SHELL OPTIONS ---- #
# ---- Defaults ---- #

# NOTE! THIS MUST MATCH PARAMS IN const_sim_params_inputs!
restore_pickle_cmdline_opt=false
restore_pickle_cmdline_name=""
PoM='python' #'matlab'  # Signalling matlab attempts to use it for orbit propagation & access calculation

CASE_NAME="NONE"  # Don't replace here; replace using "--use NEW_CASE_DIR_NAME" as flag and value on CLI
OPS_CASE="NONE" # USE TBD
SCENARIO="NONE" # USE TBD

RECOMPUTE_ALL=false
RECOMP_ORBIT_PROP=false
RECOMP_ORBIT_LINK=false
STANDALONE_GP=false
GROUND_ONLY=false
SATELLITE_ONLY=false
ipdb=''

# ---- Accept user command line input ---- #
skip=0
if (( $# > 0 ));                # seq will count from 1 to 0 if we let it, so nix if 0
then
    for i in `seq 1 $#`;        # iterate over all arguments
    do
        if (( skip > 0 )) ;     # if the prior iteration was a flag with arguments, skip that number of arguments
        then
            (( skip-=1 ))
            continue
        fi

        # Evaluate for a flag & set variables as appropriate
        if [ "${!i}" = "--help" ]; 
        then 
            echo "To call, do so in this manner: ./runner_const_sim.sh [--flag [arg1 [arg2 []]]"
            echo "With no flags or arguments, defaults are used, including the nominal use case."
            echo "Available flags:"
            printf '%s\t\t%s\n' "--ground_sim" "Starts only ground simulation (GP, Ground Stations)"
            printf '%s\t\t%s\n' "--satellite" "Starts standalone satellite simulation"
            printf '%s\t\t%s\n' "--rem_gp" "Starts standalone GP server in background before launching sim."
            printf '%s\t\t%s\n' "--F_all" "Forces all modules to be recomputed, rather than using previously computed (supposedly identical) versions of input files."
            printf '%s\t\t%s\n' "--F_prop" "Forces propagation module to be recomputed, rather than using previously computed (supposedly identical) version."
            printf '%s\t\t%s\n' "--F_link" "Forces link module to be recomputed, rather than using previously computed (supposedly identical) version."
            printf '%s\t\t%s\n' "--fromPkl" "Skips the Orbit Propagation Phase"
            printf '%s\t\t%s\n' "--ipdb" "Starts all modules with IPDB"
            printf '%s\t\t%s\n' "--use [arg]" "Supply the folder-name of the use case under circinus/inputs/cases/[use case]"
            exit 0
        fi
        if [ "${!i}" = "--ground" ];         then GROUND_ONLY=true;                   echo "Starting only ground simulation (GP, Ground Stations): $GROUND_ONLY"; fi
        if [ "${!i}" = "--satellite" ];      then SATELLITE_ONLY=true;                echo "Starting only satellite simulation: $SATELLITE_ONLY"; fi
        if [ "${!i}" = "--rem_gp" ];         then STANDALONE_GP=true;                 echo "Starting standalone GP server in background: $STANDALONE_GP"; fi
        if [ "${!i}" = "--F_all" ];          then RECOMPUTE_ALL=true;                 echo "Forcing recomputation of all modules: $RECOMPUTE_ALL "; fi
        if [ "${!i}" = "--F_prop" ];         then RECOMP_ORBIT_PROP=true;             echo "Forcing recomputation orbit propagation module: $RECOMP_ORBIT_PROP "; fi
        if [ "${!i}" = "--F_link" ];         then RECOMP_ORBIT_LINK=true;             echo "Forcing recomputation orbit link module: $RECOMP_ORBIT_LINK "; fi
        if [ "${!i}" = "--recomp" ];         then RECOMPUTE_ALL=true;                 echo "Forcing recomputation of all modules: $RECOMPUTE_ALL "; fi
        if [ "${!i}" = "--fromPkl" ];        then h=$((i+1)); restore_pickle_cmdline_opt=true; restore_pickle_cmdline_name="${!h}"; ((skip=1)); echo "restore_pickle_cmdline_opt from $restore_pickle_cmdline_name"; fi
        if [ "${!i}" = "--ipdb" ];    then ipdb=' -m ipdb -c continue'; echo "Running with IPDB enabled for exceptions "; fi
        if [ "${!i}" = "--use" ];     then h=$((i+1)); CASE_NAME="${!h}"; ((skip=1)); echo "Use case: $CASE_NAME"; fi
    done
fi

if [ "$CASE_NAME" == "NONE" ]; then
    echo "Error, use '--use CASE_NAME' to indicate which simulation case, replacing 'CASE_NAME' with your case name.  You entered: $CASE_NAME"
    exit 0
fi


# ---- END SHELL OPT ---- #

 
# ---------------------------- PATHS AND FILE NAMES  ---------------------------- #

#PATH TO LOCATION OF THIS SCRIPT (FROM WHICH ALL OTHER PATHS ARE RELATIVE).   # yea i know we could use relative paths, but they aren't clear. This is effectively relative, clear, and not dependent on being in the right directory.
CIRCINUS_PATH=$PWD/..

# ---- STD INPUT FILES ---- #
PATH_TO_INPUTS=$CIRCINUS_PATH/inputs
PATH_TO_CASE=$PATH_TO_INPUTS/cases/$CASE_NAME

# gp_general_inputs_r=$PATH_TO_CASE/gp_general_params_inputs.json  
# const_sim_params_inputs_r=$PATH_TO_CASE/const_sim_params_fullday.json  
# prop_inputs_r=$PATH_TO_CASE/orbit_prop_inputs.json
# link_inputs_r=$PATH_TO_CASE/orbit_link_inputs.json
# ---- END STD INPUT FILES ---- #


# ---- MODULE PATHS ---- #
PATH_TO_MODULES=$CIRCINUS_PATH/source                           # a bit silly to do this in two lines here, but keeps the pattern
           
ORBIT_PROP_PATH=$PATH_TO_MODULES/circinus_orbit_propagation
ORBIT_LINK_PATH=$PATH_TO_MODULES/circinus_orbit_link_public
CIRCINUS_SIM_PATH=$PATH_TO_MODULES/circinus_sim

# These two only used directly for cleanup (then referenced w/in other modules later)
GP_PATH=$PATH_TO_MODULES/circinus_global_planner  
ORBIT_VIZ_PATH=$PATH_TO_MODULES/circinus_orbit_viz
# ---- END MODULE PATHS ---- #  


# ---- AUTOGENERATED FILES ---- #
PATH_TO_AUTOGEN=$PATH_TO_CASE/autogen_files
mkdir $PATH_TO_AUTOGEN                      &>/dev/null        # Quietly create if necessary
mkdir $PATH_TO_CASE/output_files            &>/dev/null        # Quietly create if necessary
mkdir $PATH_TO_CASE/output_files/logs       &>/dev/null        # Quietly create if necessary
mkdir $PATH_TO_CASE/output_files/pickles    &>/dev/null        # Quietly create if necessary
mkdir $PATH_TO_CASE/output_files/plots      &>/dev/null        # Quietly create if necessary

rm $PATH_TO_CASE/output_files/logs/sim_sats.log &>/dev/null    # Clear, as run specific

prop_data_r=$PATH_TO_AUTOGEN/orbit_prop_data.json
data_rates_r=$PATH_TO_AUTOGEN/data_rates_output.json
# ---- END AUTOGENERATED FILES ---- #


# ---- CLEANUP unused submodules, quietly ---- #
rm -rf $GP_PATH/circinus_tools &>/dev/null
rm -rf $ORBIT_LINK_PATH/circinus_tools &>/dev/null
rm -rf $ORBIT_PROP_PATH/circinus_tools &>/dev/null
rm -rf $ORBIT_VIZ_PATH/circinus_tools &>/dev/null
rm -rf $CIRCINUS_SIM_PATH/circinus_tools &>/dev/null
# At the moment, we replace these at the end to keep the peace with git. TODO - replace with a proper file existence check instead of the try/catch for the module import
# ---- END Cleanup ---- #


if [ $restore_pickle_cmdline_opt = true ]
then
    restore_pickle_cmdline_arg="$restore_pickle_cmdline_name"
else
    restore_pickle_cmdline_arg=
fi


# --------------------------------- EXECUTION  --------------------------------- #

# -------- ORBIT PROPAGATION  -------- #
if [ ! -f $prop_data_r ] || [ $RECOMP_ORBIT_PROP == true ] || [ $RECOMPUTE_ALL == true ]; # Avoid recomputing if it exists, unless told otherwise
then
    printf "Orbit Propagation Calculations...\n\n"
    cd $ORBIT_PROP_PATH/python_runner &>/dev/null
    printf "\nrunning circinus_orbit_propagation:\npython$ipdb runner_orbitprop.py --inputs_location $PATH_TO_INPUTS --case_name $CASE_NAME --prop_and_accesses_language $PoM\n\n"
    python $ipdb runner_orbitprop.py --inputs_location $PATH_TO_INPUTS --case_name $CASE_NAME --prop_and_accesses_language $PoM
    echo "$ORBIT_PROP_PATH\n"

else
    printf "Skipping Orbit Propagation Calculation, exists...\n\n"
fi
if [ ! -f $prop_data_r ]; then echo "Orbit Propagation Calc Failed, exiting..."; exit 1; fi


# -------- ORBIT LINK CALCULATOR  -------- #
if [ ! -f $data_rates_r ] || [ $RECOMP_ORBIT_LINK == true ] || [ $RECOMPUTE_ALL == true ]; # Avoid recomputing if it exists, unless told otherwise
then
    printf "Orbit Link Calculations...\n\n"
    cd $ORBIT_LINK_PATH/python_runner/ &>/dev/null
    printf "\nrunning circinus_orbit_link_public:\npython$ipdb runner_orbitlink.py --inputs_location $PATH_TO_INPUTS --case_name $CASE_NAME --link_calculator_language $PoM\n\n"
    python $ipdb runner_orbitlink.py --inputs_location $PATH_TO_INPUTS --case_name $CASE_NAME --link_calculator_language $PoM


else
    printf "Skipping Orbit Link Calculation, exists...\n\n"
fi
if [ ! -f $data_rates_r ]; then echo "Orbit Link Calc Failed, exiting..."; exit 1; fi


if [ $STANDALONE_GP == true ]; # Avoid recomputing if it exists, unless told otherwise
then
    # ./run_ind_gp.sh > /dev/null 2>&1 &    # allowing this to show is more indicative of progress to user
    ./run_ind_gp.sh &
    sleep 5 # time to spin up
fi

# -------- SIMULATION  -------- #
cd  $CIRCINUS_SIM_PATH/python_runner/
# replace 'python' with 'mprof run -M' (after pip installing memory_profiler) to track memory use; afterwards, 'mprof plot' in the python folder will display
python $ipdb runner_const_sim.py --inputs_location $PATH_TO_INPUTS --case_name $CASE_NAME --rem_gp $STANDALONE_GP --ground_sim $GROUND_ONLY --satellite $SATELLITE_ONLY --restore_pickle "$restore_pickle_cmdline_arg"
    # python -m cProfile


# ---- Replace unused submodule empty directories, quietly ---- #
# At the moment, we replace these at the end to keep the peace with git.
mkdir $GP_PATH/circinus_tools &>/dev/null
mkdir $ORBIT_LINK_PATH/circinus_tools &>/dev/null
mkdir $ORBIT_PROP_PATH/circinus_tools &>/dev/null
mkdir $ORBIT_VIZ_PATH/circinus_tools &>/dev/null
mkdir $CIRCINUS_SIM_PATH/circinus_tools &>/dev/null
# ---- END de-cleanup ---- #
