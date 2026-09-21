# Getting Started

This guide assumes you have never used Jupyter, Python or R before. If you have,
skip to [Running a script](#running-a-script-without-a-notebook).

---

## Setting up

Python, R and JupyterLab are already installed for you. All you need is the repo
and the packages the notebooks use.

### 1. Start your server

Go to **https://workshop.nmfs-openscapes.2i2c.cloud** and log in with the
password you were given.

The first start takes a minute or two while your server is created. When it is
ready you land in JupyterLab: a file browser down the left, and a Launcher tab
of big tiles in the middle. Everything below happens in there.

### 2. Open a terminal

These commands are typed into a terminal, not into a notebook. There are two
ways to open one in JupyterLab -- either is fine:

- **From the Launcher:** the Launcher is the tab of big tiles you land on. Under
  **Other**, click **Terminal**. If no Launcher is open, click the **+** button
  at the top of the file browser on the left to get one.
- **From the menu:** **File > New > Terminal**.

Either way, a panel opens in a new tab. That is your terminal -- type into it
and press Enter.

### 3. Get the repo

It may already be there. Look first:

```bash
ls
```

That lists the folders where you are standing. **If you see
`hackathon-shared-repo`**, you already have it -- step into it and pull anything
added since:

```bash
cd hackathon-shared-repo
git pull
```

**If you do not see it**, download it:

```bash
git clone https://github.com/NMFS-PAM-Glider/hackathon-shared-repo.git
cd hackathon-shared-repo
```

Either way you should now be inside the repo. Check with `pwd` -- the path it
prints should end in `hackathon-shared-repo`.

### 4. Install the packages

```bash
pip install -r requirements.txt
```

And, if you want to run the R notebooks:

```bash
Rscript install.R
```

Running these when the packages are already present is safe -- they just report
that there is nothing to do.

That is the whole setup. Open the `notebooks` folder in the file browser on the
left and start with `01_hello_world_python.ipynb`.

---

## Running your first notebook

1. In the file browser on the left, double-click the **`notebooks`** folder.
2. Double-click **`01_hello_world_python.ipynb`**.
3. Look at the **top-right corner** of the notebook. It should say `Python 3`.
4. From the menu, choose **Run > Run All Cells**.

Output appears underneath each grey code box. That is it -- you have run code.

To run one cell at a time instead, click a cell and press **Shift + Enter**.

### Choosing the right kernel

The "kernel" is the language the notebook runs in. This is the single most
common thing to get wrong.

| Notebook name ends in | Kernel must say |
|---|---|
| `_python.ipynb` | `Python 3` |
| `_r.ipynb` | `R` |

The kernel name sits in the **top-right corner** of an open notebook. If it is
wrong, click it and pick the right one from the list.

If R code gives you an error like `NameError` or `invalid syntax`, you are
almost certainly running it with the Python kernel.

### What order to go in

| Notebook | What it covers | Needs internet? |
|---|---|---|
| `01_hello_world_*` | Check your setup works | No |
| `02_files_and_github_*` | Reading and writing files, git | No |
| `03_aquaview_stac_*` | Pulling real data from AQUAVIEW | Yes |
| `04_glider_satellite_*` | Comparing a glider track with satellite data | Yes |
| `05_hackathon_data_*` | Opening the hackathon data files | No |
| `06_aquaview_discovery_*` | AQUAVIEW workshop -- follow along in the session | Yes |

Each one exists twice, once for Python and once for R. They do the same thing,
so pick whichever language you prefer -- or read both to compare.

Notebooks 01-03 are short and build on each other. Notebook 04 is longer -- a
complete real-world workflow contributed by NOAA CoastWatch, comparing a glider
track against satellite chlorophyll, temperature and salinity.

See [`notebooks/README.md`](../notebooks/README.md) for what each one covers.

---

## Running a script without a notebook

Not everything has to be a notebook. From a terminal, at the top level of the
repo:

```bash
# Python
python3 your-name-your-feature/your_script.py

# R
Rscript your-name-your-feature/your_script.R
```

The general shape is `python3 <path to the file>` or `Rscript <path to the file>`.
The path is relative to wherever you are standing in the terminal, so `cd` to the
top of the repo first if you are not already there.

### Why paths sometimes break

A notebook runs from the folder *it* lives in, not from the top of the repo. So
inside `notebooks/`, a file at `docs/code_standards.md` is not found -- it is
`../docs/code_standards.md` from there.

Every notebook here works around this by finding the top of the repo once:

```python
# Python
from pathlib import Path
REPO = Path.cwd()
if REPO.name == "notebooks":
    REPO = REPO.parent
```

```r
# R
repo <- getwd()
if (basename(repo) == "notebooks") repo <- dirname(repo)
```

Copy that into your own notebooks and build paths from `REPO` / `repo`.

---

## Working with large data files

Research datasets get big, and loading one carelessly is the quickest way to
crash a notebook. A CSV needs several times its file size in memory to load, so
a 250 MB file can easily need more than a gigabyte.

Read only the columns you need:

```python
pd.read_csv(path, usecols=["time", "depth", "temperature"])
```

or work through the file in pieces:

```python
for chunk in pd.read_csv(path, chunksize=100_000):
    ...
```

Start with the smallest file you can that still answers your question, and only
scale up once the code works.

Keep large files out of git. Common data formats are ignored -- see
[`.gitignore`](../.gitignore) -- because GitHub rejects files over 100 MB and a
bloated repository is slow for everyone to clone.

---

## Saving your work

Your work is not safe until it is pushed to GitHub. Everyone works on their own
branch in this repo, so make one for yourself before you start:

```bash
git checkout -b your-name-your-feature
```

Then, as you go:

```bash
git add .
git commit -m "a short note about what you did"
git push -u origin your-name-your-feature    # plain `git push` after the first time
```

The full walkthrough -- branching, pushing, and opening a pull request so your
work reaches `main` -- is in the [main README](../README.md).

Two habits worth having:

- **Clear notebook outputs before committing.** A notebook saves its outputs
  inside the file, so simply re-running one shows up as a change. *Kernel >
  Restart Kernel and Clear Outputs* keeps pull requests readable.
- **Keep your work in your own folder**, named `your-name-your-feature`, as the
  README asks. And follow [`code_standards.md`](code_standards.md): every script
  needs a header saying what it is, how to run it, and what goes in and out. In a
  notebook, put that header in the first markdown cell -- notebooks 01-03 show
  the pattern.

---

## When something goes wrong

| Symptom | Likely cause |
|---|---|
| `NameError` or `invalid syntax` in an R notebook | Wrong kernel -- check the top-right corner says `R` |
| `FileNotFoundError` / `cannot open file` | Path is relative to `notebooks/`, not the repo root -- see above |
| `ModuleNotFoundError` | Package missing -- run `pip install -r requirements.txt` |
| `there is no package called ...` | Run `Rscript install.R` |
| No `R` option in the kernel list | Refresh the page first; if it is still missing, ask an organiser |
| The kernel dies loading a file | Out of memory -- see [Working with large data files](#working-with-large-data-files) |

Still stuck? Open an issue on the repo, or ask an organiser.
