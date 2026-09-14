# Glider Rodeo Hackathon Repository: hackathon-shared-repo
A place to share hackathon code projects.

**Repository:** https://github.com/NMFS-PAM-Glider/hackathon-shared-repo

## Quick start

**1. Start your server:** https://workshop.nmfs-openscapes.2i2c.cloud

Log in with the provided password. That gives you JupyterLab in your browser,
with Python and R already installed.

**2. Set up the repo.** Open a terminal in JupyterLab (**File > New > Terminal**,
or the **Terminal** tile on the Launcher) and run:

```bash
ls                                  # already see hackathon-shared-repo? skip the clone
git clone https://github.com/NMFS-PAM-Glider/hackathon-shared-repo.git
cd hackathon-shared-repo

pip install -r requirements.txt     # Python
Rscript install.R                   # R, only if you want the R examples
```

The packages above are all you need to add.

**3. Start working.** Open `notebooks/` in the file browser and work through them
in order, starting with `01_hello_world_python.ipynb` or
`01_hello_world_r.ipynb`.

New to Jupyter, Python or R? Read **[docs/getting_started.md](docs/getting_started.md)**
first.

## What is in here

| Notebook (Python and R) | What it covers |
|---|---|
| `01_hello_world_*` | Check your setup works |
| `02_files_and_github_*` | Read and write files, and get your work onto GitHub |
| `03_aquaview_stac_*` | Pull real ocean data from the public AquaView catalogue |
| `04_glider_satellite_*` | Compare a glider track against satellite observations |
| `05_hackathon_data_*` | List the hackathon data folder and open a file |
| `06_aquaview_discovery_*` | **AQUAVIEW workshop** -- follow along during the session |

Every example exists twice -- once in Python, once in R -- so use whichever
language you prefer.

```
notebooks/        the worked examples, 01-05, plus workshop notebooks
docs/             getting started guide and code standards
requirements.txt  Python packages
install.R         R packages
```

Notebooks 01-03 are short and build on each other. 04 is a longer, real-world
workflow contributed by NOAA CoastWatch, and 05 opens the hackathon data. **06 is
for the live AQUAVIEW session -- open it and follow along when that runs.** See
[notebooks/README.md](notebooks/README.md) for what each one covers.

## The hackathon data

The Glider Rodeo data is not in this repository -- the files are far too big for
git. It lives in a shared folder alongside it.

**`05_hackathon_data_*`** opens it: it lists what is there and reads a file. One
line at the top of that notebook says where to look, so if your copy is
elsewhere, change it there. See [notebooks/README.md](notebooks/README.md) for
what each deployment folder contains and which files are safe to open whole.

## Adding your own work

Put it in a folder named `your-name-your-feature`, include a `README.md`
describing it, and follow [docs/code_standards.md](docs/code_standards.md).
[template_project/](template_project/) has a starting point you can copy. Then
open a pull request using the walkthrough below.

---

## Instructions for working on your own branch

Everyone works in this one shared repository, each on their own branch. No
forking needed.

> **Before you start:** you need push access. If step 4 fails with a permissions
> error, ask an organiser to add you as a collaborator on the repo.

### 1. Clone the Repository:
Go to your terminal, navigate to where you want this repository to live on your machine, and run `git clone https://github.com/NMFS-PAM-Glider/hackathon-shared-repo.git`. Then move into it with `cd hackathon-shared-repo`.

#### 1.1 What You Did:
You just pulled the hackathon-shared-repo onto your computer so that you can start working on it. You are currently on the `main` branch -- the shared one that everybody sees.

### 2. Create Your Own Branch:
Do not work directly on `main`. Make yourself a branch named the same way you will name your folder: `git checkout -b your-name-your-feature`. For example, `git checkout -b john-doe-data-visualizer`. Run `git branch` afterwards to check -- the branch with the `*` next to it is the one you are on.

#### 2.1 What You Did:
You made your own private line of work inside the shared repository. Anything you commit now lands on your branch and nowhere else, so you cannot break `main` or trip over anybody else's work. This is the space to add your cool, new, exciting, ground-breaking, paradigm-shifting tools!

### 3. Make Your Changes:
First, create a folder and title it: your-name-your-feature. For example, john-doe-data-visualizer. Make sure that everything you created or do, stays within this folder otherise your work will not be accepted (until your correct this :D). Within your folder, make a file called README.md, this is space for your to write a quick description of what your code is supposed to do and explain briefly how your code is supposed to work. Write any code you want to write within your folder, test it, be happy with it, and then move onto the next step. (Make sure to commit regularly with quality commit messages)!

#### 3.1 What You Did:
You just did some awesome coding either on your own or with the help of a chatbot assistant, great work!

### 4. Push Your Branch to Github:
Now that you've made your changes, you can add and commit them. Hopefully you've been doing this as you go, but it's okay if this is the first time. From the hackathon-shared-repo directory run `git add .`. This command will stage all the changes in the current directory. Run `git status` and make sure that all the files you made or modified are green, this means they are ready to be committed. Now run `git commit -m "your message describing what you did."` And finally, the first time you push a new branch, run `git push -u origin your-name-your-feature`. After that first time, plain `git push` is enough.

#### 4.1 What You Did:
You just put your branch up on github, where it is backed up and other people can see it. You rock! Your work is still only on your branch -- `main` has not changed.

### 5. Open a Pull Request:
Go to the repository on github. You should see a yellow banner near the top saying your branch had recent pushes, with a green 'Compare & pull request' button -- click it. (If the banner is gone, click the 'Pull requests' tab, then 'New pull request', and choose your branch.) Check that it says it will merge `your-name-your-feature` into `main`. Write a description of the changes you made and review your code. I highly suggest reviewing your code here because I often catch bugs in this stage. Finally, press 'Create pull request'.

#### 5.1 What You Did:
You proposed your work for the maintainer (me) to view then accept / reject. If you 1. did your work entirely in your folder, 2. added a README.md to your folder, and 3. made sure to include a code spec in your script(s), then I am pretty dang sure that I am about to accept your contribution, great job!!!

### 6. Keeping Up To Date (optional):
If other people's work gets merged into `main` while you are still going, you can pull it into your branch with `git pull origin main`. This is worth doing before you open your pull request, so yours merges cleanly.
