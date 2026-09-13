# Command Line Cheat Sheet
##  For working in the JupyterHub Terminal



## task: Configure basic git information
command: 	$ git config --global user.name "Attendee Name"
		    $ git config --global user.email "attendee@hackweek.com"
		    $ git config --global pull.rebase true
example: 	$ git config --global user.name "John Doe"
		    $ git config --global user.email "john.doe@hackweek.com"
		    $ git config --global pull.rebase true

## task: Verify your git configuration
command:    $ git config --list
example return: user.name=Attendee Name
        		user.email=attendee@hackweek.com
        		pull.rebase=true

## task: Get GitHub Credentials
command: $ gh-scoped-creds
example return:	You have 15 minutes to go to https://github.com/login/device and enter the code: XXXX-XXXX
		Waiting......
next step: Click on the 'https://github.com/login/device' link, then copy in the code

## task: Clone a GitHub Repo
command: $ git clone https://github.com/myRepo.git
example: $ git clone https://github.com/NMFS-PAM-Glider/hackathon-shared-repo.git

## task: Push Changes to a Repo (this will consist of a series of commands
commands: 	$ cd hackathon-shared-repo  # Ensure you are in your intended directory
		    $ git status  	# Check on the status- you should have files to add
		    $ git add -A 	# to add all changed files
		    $ git commit -m "Summarize changes here"
		    $ git push
 	

## task:	Remove a GitHub repository from your JupyterHub environment
command: 	$ rm -rf repository-name
example: 	$ rm -rf hackathon-shared-repo





