# SPRINT
**S**cheduling
**P**lanning
**R**outing
**I**nter-satellite
**N**etworking
**T**ool

Incorporating the **C**onstellation **I**nvestigation **R**epository with **C**ommunications, **I**nter-agent **N**etworking, **U**ncertainty, and **S**cheduling

# General Setup

1. Clone the repo: `git clone git@github.com:MIT-STARLab/SPRINT.git`
1. Init the appropriate submodules: 
    1. `cd SPRINT/source` 
    1. `git submodule init circinus_global_planner circinus_orbit_link_public circinus_orbit_propagation circinus_orbit_viz circinus_sim circinus_tools`
    1. `git submodule update`
1. Set up your environment:
    1. Install and configure your default `python` and pip to Python **3.6**, (recommended in a virtual environment, see next step).
        1. Recommended: Direct installation, if needed: Download from https://www.python.org/downloads/. Note that the global planner code is currently tested with Python 3.6.7.
        1. Not recommended: alternatively Homebrew, [pyenv to set to 3.6](https://github.com/pyenv/pyenv).
        1. Pick your poison and stick with it or it'll get messy.
        1. Confirm your version of Python (`python --version`) & location of the installation (`which python`) is the same for all subsequent steps.
        1. Consider upgrading pip: `python3.6 -m pip install --upgrade pip`
    1. Make a virtual environment:
        1. Install virtualenv: `python3.6 -m pip install virtualenv`
        1. Create virtual environment: <br>OS X: `python3.6 -m virtualenv --python=/usr/local/bin/python3.6 venv_dir/`, <br>Windows: `virtualenv --python=/c/Users/STARLab/AppData/Local/Programs/Python/Python35/python.exe venv_dir`, <br>Ubuntu: `virtualenv -p /usr/bin/python3.6 venv_dir` <br>*`python=` reflects path to the Python 3.6 executable* <br>*`venv_dir` is the directory of your choosing to intall this particular virtualenv instance (not in git repo)*
        1. Activate the virtual environment: <br>OS X or Ubuntu: `source venv_dir/bin/activate`, <br>Windows: `source venv_dir/Scripts/activate`
    1. Install required python packages.
        1. cd to SPRINT base directory
        2. `pip install -r requirements.txt`
    1. Install Gurobi:
        1. Download and install [Gurobi 8.0.0](http://www.gurobi.com/downloads/gurobi-optimizer)
        1. Acquire and activate Gurobi License ([Academic is free if appropriate](https://www.gurobi.com/downloads/end-user-license-agreement-academic/))
    1. Framework setting:
        1. `nano ~/.matplotlib/matplotlibrc`
        1. add line: `backend: TkAgg`

# Simulation Pipeline Demo:            
1. Navigate to `SPRINT/scripts`
1. Run simulation: <br>
    a. `./run_const_sim.sh --use orig_circinus_zhou` to specify a case corresponding to `inputs/cases/orig_circinus_zhou`.<br>
    b. `./run_const_sim.sh --help` for a description of the other options.<br>

# Submodule dependencies
* [circinus_global_planner](https://github.com/MIT-STARLab/circinus_global_planner)
* [circinus_orbit_link](https://github.com/MIT-STARLab/circinus_orbit_link)
* [circinus_orbit_propagation](https://github.com/MIT-STARLab/circinus_orbit_propagation)
* [circinus_orbit_viz](https://github.com/MIT-STARLab/circinus_orbit_viz)
* [circinus_sim](https://github.com/MIT-STARLab/circinus_sim)
* [circinus_tools](https://github.com/MIT-STARLab/circinus_tools)

These should be managed as if they are independent and up to date with their own master, before committing the folder from the the SPRINT main repository (which then tracks the commit of the subrepo).

# History
SPRINT was initiated as CIRCINUS, by [apollokit](https://github.com/apollokit)
