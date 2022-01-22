#! /bin/bash
printf "running: $0\n"
printf "IN INDGP"
# ---------------------------- PATHS AND FILE NAMES  ---------------------------- #

#PATH TO LOCATION OF THIS SCRIPT (FROM WHICH ALL OTHER PATHS ARE RELATIVE).
CIRCINUS_PATH=$PWD/..

# ---- STD INPUT FILES ---- #
PATH_TO_INPUTS=$CIRCINUS_PATH/inputs

# ---- MODULE PATHS ---- #
PATH_TO_MODULES=$CIRCINUS_PATH/source
           

# --------------------------------- EXECUTE GP  --------------------------------- #
cd $PATH_TO_MODULES/central_global_planner

python $ipdb cgp_main.py --inputs_location $PATH_TO_INPUTS
