# CIRCINUS

**C**onstellation
**I**nvestigation
**R**epository with
**C**ommunications,
**I**nter-agent
**N**etworking,
**U**ncertainty, and
**S**cheduling

original `Comm_constellation_MDO` repo: [https://github.com/ebclements/Comm_constellation_MDO](https://github.com/ebclements/Comm_constellation_MDO)

# Setup

Make sure to do a recursive clone of this repo, to get all the submodules. E.g. `git clone --recursive git@github.mit.edu:star-lab/CIRCINUS.git`

# Updating git submodules

Working with git submodules can be a bit confusing. Often when you cd into the submodule directory you'll find the git repo in a detached state, saying something like `HEAD detached at af4512d` at the command line. This is alright, and is related to the fact that git thinks of submodules as a specific commit for a remote repo, and not a branch. However, we have added branch information in .gitmodules file in CIRCINUS that specifies which branch to track for the submodules. In this case you can use the command: `git submodule update --remote` to update to the most recent commit of the desired branch for that submodule. In CIRCINUS there are actually submodules within the submodules in many cases, so you can use `git submodule update --recursive --remote` to recursively update all layers of submodules. Note here that when you directly pull the latest commit on a submodule branch with this method, the commit in the repo containing the submodule may not have updated its commit history for that submodule, and this will be reflected with the "new commits" indicator when you run `git status`.

For pushing from a detached HEAD to the master branch at origin: `git push origin HEAD:master`
