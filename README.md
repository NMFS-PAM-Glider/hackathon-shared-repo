# hackathon-shared-repo
A place to share hackathon code projects.

**Repository:** https://github.com/NMFS-PAM-Glider/hackathon-shared-repo

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/NMFS-PAM-Glider/hackathon-shared-repo/main)

## Quick start

**Click the badge above.** It builds the full environment in the cloud -- Python,
R, and every package -- and opens JupyterLab in your browser. Nothing to install.

Then open `notebooks/` and work through them in order. Start with
`01_hello_world_python.ipynb` or `01_hello_world_r.ipynb`.

New to Jupyter, Python or R? Read **[docs/getting_started.md](docs/getting_started.md)**
first -- it assumes no prior experience.

## What is in here

| Notebook (Python and R) | What it covers |
|---|---|
| `01_hello_world_*` | Check your environment works |
| `02_files_and_github_*` | Read and write files, and get your work onto GitHub |
| `03_aquaview_stac_*` | Pull real ocean data from the public AquaView catalogue |
| `04_hackathon_data_*` | Load the hackathon's own dataset |

Every example exists twice -- once in Python, once in R -- so use whichever
language you prefer.

```
binder/      environment definition (Binder builds from this)
notebooks/   the starter examples, 01-04, Python and R
tutorials/   longer worked examples contributed by the community
scripts/     one-time setup, including the data download
data/        the dataset lives here (not committed to git)
docs/        getting started guide and code standards
```

Once you have worked through 01-04, [tutorials/](tutorials/) has longer,
real-world examples -- starting with comparing a glider track against satellite
observations, in both Python and R.

## Getting the hackathon dataset

The **Glider Rodeo** dataset -- eight glider deployments from January 2026 -- lives
in a public Google Cloud bucket. No login or credentials needed.

See what is available:

```bash
python3 scripts/fetch_hackathon_data.py
```

Then download a deployment (the whole set is 1.3 GB, so start with one):

```bash
python3 scripts/fetch_hackathon_data.py sg274_20260128
```

See [data/README.md](data/README.md) for what each deployment contains. Notebooks
01-03 do not need the dataset at all, and notebook 04 falls back to a bundled
sample, so you can start straight away.

## Adding your own work

Put it in a folder named `your-name-your-feature`, include a `README.md`
describing it, and follow [docs/code_standards.md](docs/code_standards.md). Then
open a pull request using the walkthrough below.

---


## Instructions for forking and creating a pull request

### 1.Fork the Repository: 
While on this page, look to the upper right corner. You should see three buttons labeled: 'watch', 'fork', and 'star'. As you may have guessed, 
you should click the 'fork' button. You will be taken to a new page with some options about how to fork the repository; these options included changing the name, or bringing down branches other than main. Do not mess with the default settings on this page unless you have a specific reason to do so. At the bottom of the page, press the green 'create fork' button. 

#### 1.1 What You Did:
In step one, you made a copy of our hackathon-shared-repo to your github. You have full ownership of this copy and you can do whatever you want to the copy. This copy is the space that you have to add your cool, new, exciting, ground-breaking, paradigm-shifting tools to our shared repository!

### 2. Check the Fork:
Once you created your fork, github should automatically take your to your fresh fork. Take a look and see if you're looking at your fork. You should see in the very top left hand corner of github that you are now in {your_github_username}/hackathon-shared-repo (instead of NMFS-PAM-Glider/hackathon-shared-repo where you were before forking). If this looks right, let's move onto the next step

### 3. Clone the Fork onto Your Machine:
In the middle upper right hand of your github screen, you should see a green button titled 'clone'. Click this button and select a method to clone the repository. I typically use 'HTTPS'. Go ahead and copy the github link. Now, go to your terminal, navigate to where you want this repository to live on your machine and use `git clone https://github.com/{your_github_username}/hackathon-shared-repo.git` (REMEMBER TO SUB IN YOUR GITHUB USERNAME -- you are cloning *your fork*, not the original repo at NMFS-PAM-Glider)!

#### 3.1 What You Did: 
You have just pull the hackathon-shared-repository onto your computer so that you can start working on it.

### 4. Make Your Changes:
First, create a folder and title it: your-name-your-feature. For example, aksel-sloan-data-visualizer. Make sure that everything you created or do, stays within this folder otherise your work will not be accepted (until your correct this :D). Within your folder, make a file called README.md, this is space for your to write a quick description of what your code is supposed to do and explain briefly how your code is supposed to work. Write any code you want to write within your folder, test it, be happy with it, and then move onto the next step. (Make sure to commit regularly with quality commit messages)!

#### 4.1 What You Did:
You just did some awesome coding either on your own or with the help of a chatbot assistant, great work! 

### 5. Push Your Changes to Your Github:
Now that you've made your changes, you can add and commit your changes. Hopefully you've been doing this as you go, but it's okay if this is the first time. Get to your the hackathon-shared-repo directory and run `git add .`. This command will stage all the changes in the current directory. Run `git status` and make sure that all the files you made or modified are green, this means they are ready to be committed. Now run `git commit -m "your message describing what you did." And finally, run `git push`. Git push is what actually sends your new code up to github! 

#### What You Did:
You just put your changes up on your personal github. You rock! 

### 6. Make a Pull Request to the Original Repo:
Now that your changes are on your github, you need to move to the official hackathon github. First, press the 'sync fork' button right under the green "code" button to make sure that, besides the changes you made, your repo matches the official repo. Then, press the 'contribute' button right next to the 'sync fork' button. A new popup window should appear and you can press the big green 'open pull request' button. Now you should be taken to a new page where you can write a description of the changes you made and review your code. I highly suggest reviewing your code here because I often catch bugs in this stage. Finally, press 'create pull request'. This button is the one that actually sends your changes to me for review. 

#### What You Did:
You uploaded your code to the original repository for the maintainer (me) to view then accept / reject. If you 1. did your work entirely in your folder, 2. added a README.md to your folder, and 3. made sure to include a code spec in your script(s), then I am pretty dang sure that I am about to accept your contribution, great job!!!
