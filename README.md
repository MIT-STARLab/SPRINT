# SPRINT

**S**cheduling
**P**lanning
**R**outing
**I**nter-satellite
**N**etworking
**T**ool

# General Setup

1. Clone the repo: `git clone --recursive git@github.com:apollokit/circinus.git`
1. Set up your environment:
    1. Install and configure your default `python` and pip to exactly Python **3.6**, (recommended in a virtual environment, see next step).
        1. Recommended: Direct installation, if needed: Download from https://www.python.org/downloads/. Note that the global planner code is currently tested with Python 3.6.7.
        1. Not recommended: alternatively Homebrew, [pyenv to set to 3.6](https://github.com/pyenv/pyenv).
        1. Pick your poison and stick with it or it'll get messy.
        1. Confirm your version of Python (`python --version`) & location of the installation (`which python`) is the same for all subsequent steps.
    1. Make the virtual environment:
        1. cd to your new SPRINT repo
        1. Install virtual environment executable if needed, `pip install virtualenv`
        1. Create the virtual environment and install requirements with `./create_virtualenv.sh`
            1. Note that this DOES NOT install the required matlab package needed for many SPRINT repos. See below for those instructions
        1. Activate the virtual environment: `source source_virtualenv`
    1. Install [Matlab python engine](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html?refresh=true). Last tested with Matlab 2019b.
        1. Ensure the correct version of python is enabled being referenced where you execute this installation command (pyenv is directory specific, for instance).
        2. Sudo or admin terminal will be necessary.
        3. after installation, check output of `pip freeze` to see that a line like `matlabengineforpython===R2019b` appears.
        4. install screen. Ubuntu: `sudo apt-get install screen`
        5. `nano source/
        _tools/matlab_if/interface.py`, edit `matlab_ver='NOT_SET'` in MatlabIF's init to be `matlab_ver='MATLAB_R2019b'`, according to your version.
    1. Install Gurobi:
        1. Download and install [Gurobi 8.0.0](http://www.gurobi.com/downloads/gurobi-optimizer)
        1. Acquire and activate Gurobi License ([Academic is free if appropriate](https://www.gurobi.com/downloads/end-user-license-agreement-academic/))
    1. Framework setting:
        1. `nano ~/.matplotlib/matplotlibrc`
        1. add line: `backend: TkAgg`
        
# GlobalPlanner-only Demo:
1. Setup:
    1. Init empty folder for outputs: `mkdir SPRINT/source/access_global_planner/python_runner/plots`
    1. Ensure scenario referenced by each stage in the pipeline is the same by settings at top of<br> `run_gp.sh` and `run_circinus.sh` (in `SPRINT/scripts`):<br>
        ```
        dir_opt=1day
        scen_name=zhou2017_comparison
        dir_opt_params=dlnk_and_xlnk
        ```
    1. Set solver to Gurobi (alternatively set up CPLEX instead of Gurobi above): 
        1. Navigate to: `SPRINT/inputs/1day/zhou2017_comparison/dlnk_and_xlnk` (per above settings) 
        1. Modify `const_sim_params_fullday.json` and `gp_general_params_inpus.json`:
            1. change value associated with `solver_name` to `gurobi`
1. Run:
    1. Navigate to `SPRINT/scripts`
    1. Circinus must be run first: `./run_circinus.sh`
    1. Copy output file to inputs location: `cp ../source/circinus_orbit_link/python_runner/data_rates_output.json ../inputs/1day/zhou2017_comparison/dlnk_and_xlnk/`
    1. Run Global Planner: `./run_gp.sh`

# Simulation Pipeline Demo:
1. Setup: 
    1. Init empty folder for outputs:<br>
    `mkdir SPRINT/source/circinus_sim/python_runner/logs`<br>
    `mkdir SPRINT/source/circinus_sim/python_runner/pickles`<br>
    `mkdir SPRINT/source/circinus_sim/python_runner/plots`<br>
    1. In `SPRINT/inputs/1day/zhou2017_comparison/dlnk_and_xlnk/const_sim_params_fullday.json`<br>
    set `restore_from_checkpoint` to `false` for (at least) the first run.
    1. Ensure scenario referenced at top of `scripts/run_const_sim.sh` references:<br>
        ```
        dir_opt=1day
        scen_name=zhou2017_comparison
        dir_opt_params=dlnk_and_xlnk
        ```
    1. Set solver to Gurobi (alternatively set up CPLEX instead of Gurobi above): 
        1. Navigate to: `SPRINT/inputs/1day/zhou2017_comparison/dlnk_and_xlnk` (per above settings) 
        1. Modify `const_sim_params_fullday.json` and `gp_general_params_inpus.json`:
            1. change value associated with `solver_name` to `gurobi`
            
2. Run:
    1. Navigate to `SPRINT/scripts`
    1. Circinus must be run first: `./run_circinus.sh`
    1. Copy output file to inputs location: `cp ../source/circinus_orbit_link/python_runner/data_rates_output.json ../inputs/1day/zhou2017_comparison/dlnk_and_xlnk/`
    1. Run simulation: `./run_const_sim.sh`

# Updating git submodules

In general you should use the command `git submodule update --recursive`. This checks out all the right commits for all the (possibly multiple layers of) submodules within the top git repo. `git pull` by itself won't do it.

In SPRINT there are actually submodules within the submodules in many cases, so the `--recursive` flag is needed to recursively update all layers of submodules.

Note that working with git submodules can be a bit confusing. Usually when you update submodules you'll afterwards find the submodule in a detached state, saying something like `HEAD detached at af4512d` at the command line - it's no longer on an existing branch. This is alright, and is related to the fact that git thinks of submodules as a specific commit for a remote repo, and not a branch. However, we have added branch information in .gitmodules file in SPRINT that specifies which branch to track for the submodules. In this case you can use the command: `git submodule update --recursive --remote` to update to the most recent commit of the desired branch for that submodule.  One problem here though is that when you directly pull the latest commit on a submodule branch with this method, the commit in the repo containing the submodule may not have updated its commit history for that submodule, and this will be reflected with the "new commits" indicator when you run `git status`. Basically, unless all the repos from top to bottom (through all submodules) are committed (within the parent repo) at the latest commit for the specified branch, you'll have an out of date repo somewhere. General rule to keep in mind: as long as `git status` from the top-most repo indicates no changes, your submodules are all checked out on the right commit. 

For pushing from a detached HEAD to the master branch at origin: `git push origin HEAD:master`


# History
SPRINT was initiated as CIRCINUS, by [apollokit](https://github.com/apollokit)

**C**onstellation
**I**nvestigation
**R**epository with
**C**ommunications,
**I**nter-agent
**N**etworking,
**U**ncertainty, and
**S**cheduling