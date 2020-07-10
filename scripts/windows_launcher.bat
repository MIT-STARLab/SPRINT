@ echo off
REM this script assumes you are calling from the $REPO_BASE/scripts directory
REM helpful batch string operations here: https://www.dostips.com/DtTipsStringManipulation.php#Snippets.Replace
REM ===========SETUP THE FOLLOWING VARIABLES FOR EACH COMPUTER=============
REM THIS FILE ASSUMES YOU HAVE A LOCAL FILE THAT SETS THE FOLLOWING ENVIRONMENT VARIABLES (name it windows_env_var_setup.bat to have git ignore it):
REM PY_ENV_NAME: name of python environment that runs SPRINT
REM PY_ENV_ACTIVATE_DIR: full path to activate script of your python distribution, if using Anaconda it is at C:\Users\[User Name]\Anaconda3\Scripts\activate
REM BASH_DIR: full path to the bash executable, if using git SCM, then it is usually at C:\Users\[User Name]]\AppData\Local\Programs\Git\bin\bash OR at C:\Program Files\Git\bin\bash 
REM PKL_DIR: full path (in UNIX convention, NOT windows) to the pickle you want to run from (if this isn't set, then it will run from the start)
REM ======================END SETUP VARIABLES==============================
call windows_env_var_setup.bat
REM Activate python environment
SET cur_dir_win=%~dp0
SET cur_dir_unix=%cur_dir_win:\=/%
SET cur_dir_unix=%cur_dir_unix:~0,-1%
call %PY_ENV_ACTIVATE_DIR% %PY_ENV_NAME%
REM change directory manually as needed, this is hacky for now to get the project done
REM remove carriage returns (CR) from the DOS stored version of the file
if not exist run_const_sim_win.sh (
call "%BASH_DIR%" --login -c "cd '%cur_dir_unix%'; sed 's/\r$//' run_const_sim.sh > run_const_sim_win.sh"
REM allow all acesses on new file
call "%BASH_DIR%" --login -c "cd '%cur_dir_unix%'; chmod +x run_const_sim_win.sh"
)
REM run new script
if defined PKL_DIR (
call "%BASH_DIR%" --login -c "cd '%cur_dir_unix%'; ./run_const_sim_win.sh --fromPkl %PKL_DIR%"
) else (
 call "%BASH_DIR%" --login -c "cd '%cur_dir_unix%'; ./run_const_sim_win.sh"   
)