========================================

## JupyterHUb + Github Terminal Cheat Sheet

========================================

## --- Navigate and inspect files ---

```         
pwd                         # Show current directory
ls                          # List files
ls -la                      # List all files, including hidden files
cd my-repo                  # Enter a directory
cd ..                       # Move up one directory
find . -maxdepth 2 -type f  # Find files up to 2 directories deep
cat README.md               # Print a file
less README.md              # View a file one screen at a time
```

## --- GitHub / Git: Getting a repository ---

```         
git clone https://github.com/USERNAME/REPOSITORY.git  # Clone a GitHub repo
cd REPOSITORY                                          # Enter the repo
git status                                              # Check repo status
git remote -v                                           # See connected GitHub remote
```

## --- Git: Branches ---

```         
git branch                    # List local branches
git branch -a                 # List local + remote branches
git branch --show-current     # Show current branch
git switch main               # Switch to the main branch
git switch -c my-new-branch   # Create and switch to a new branch
```

## --- Git: Get changes from GitHub ---

```         
git pull                      # Download and merge latest changes
git fetch                     # Download changes without merging
```

## --- Git: See what you've changed ---

```         
git status                    # See changed/untracked files
git diff                      # See changes that haven't been staged
git diff my_file.py           # See changes to a specific file
```

## --- Git: Save and upload your changes ---

```         
git add my_file.py            # Stage one specific file
git add .                     # Stage all changes
git commit -m "Describe changes"  # Commit staged changes
git push                      # Upload commits to GitHub
```

## For a new branch, use:

```         
git push -u origin my-new-branch
```

## --- Python / packages ---

```         
python --version              # Check Python version
which python                  # Show which Python executable is being used
pip list                      # List installed Python packages
pip install pandas            # Install a Python package
pip install -r requirements.txt  # Install packages from requirements.txt
python my_script.py           # Run a Python script
```

## --- Jupyter ---

```         
jupyter --version             # Check Jupyter version
jupyter lab                   # Start JupyterLab (if permitted)
jupyter nbconvert --to notebook --execute my_notebook.ipynb
                              # Execute a notebook from the terminal
```

=============================

## COMMON WORKFLOW

=============================

### 1. Get the repository

git clone <https://github.com/USERNAME/REPOSITORY.git> cd REPOSITORY

### 2. Check its status

git status

### 3. Get the latest version

git pull

### 4. Do your work in JupyterLab...

### 5. See what changed

git status git diff

### 6. Stage your changes

git add .

### 7. Commit your changes

git commit -m "Describe what I changed"

### 8. Upload to GitHub

git push
