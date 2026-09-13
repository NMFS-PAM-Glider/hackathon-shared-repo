# Getting Started

This guide assumes you have never used Jupyter, Python or R before. If you have,
skip to [Running a script](#running-a-script-without-a-notebook).

---

## The quickest start: Binder

Click the badge on the [main README](../README.md), or use this link:

**https://mybinder.org/v2/gh/NMFS-PAM-Glider/hackathon-shared-repo/main**

This builds the whole environment for you in the cloud -- Python, R and every
package -- and opens JupyterLab in your browser. Nothing to install.

The first launch takes a few minutes while the image builds. Later launches are
much faster.

> **Binder sessions are temporary.** After about 10 minutes of inactivity the
> session shuts down and *everything you did is erased*. Before you close the
> tab, download any file you want to keep (right-click > Download), or commit
> and push your work. See [Saving your work](#saving-your-work).

---

## Running your first notebook

Once JupyterLab is open:

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

| Notebook | What it covers | Needs internet? | Needs the dataset? |
|---|---|---|---|
| `01_hello_world_*` | Check the environment works | No | No |
| `02_files_and_github_*` | Reading and writing files, git | No | No |
| `03_aquaview_stac_*` | Pulling real data from AquaView | Yes | No |
| `04_hackathon_data_*` | Using the hackathon dataset | No | Helps, but not required |

Each one exists twice, once for Python and once for R. They do the same thing,
so pick whichever language you prefer -- or read both to compare.

### After the starter notebooks

[`tutorials/`](../tutorials/) holds longer worked examples contributed by the
community. The first one compares a glider track against satellite chlorophyll,
temperature and salinity -- a complete real-world workflow, in both Python and R.
See [`tutorials/README.md`](../tutorials/README.md).

---

## Getting the hackathon dataset

The dataset is the **Glider Rodeo** collection -- eight glider deployments from
January 2026, 1.3 GB in total. It lives in a **public** Google Cloud bucket, so
there is no login, no Google account and no credentials to set up.

You download it **once**, and after that every notebook simply reads local files.

Open a terminal -- in JupyterLab, **File > New > Terminal** -- and run this from
the top level of the repo to see what is available:

```bash
python3 scripts/fetch_hackathon_data.py
```

That prints the eight deployments and their sizes without downloading anything.
Then ask for the one you want:

```bash
python3 scripts/fetch_hackathon_data.py sg274_20260128
```

Start with a single deployment rather than `--all`. The smallest
(`sg274_20260128`) is 31 MB; everything together is 1.3 GB and takes a while.

The files land in `data/`, mirroring the folder layout of the bucket. Running the
script again is safe and quick -- anything already downloaded is skipped.

> **In Binder**, the session is erased when you close it, so your download goes
> with it. One deployment is fine to pull in Binder; for sustained work with the
> full dataset use a local clone or a persistent JupyterHub.

Notebooks 01-03 need none of this, and notebook 04 falls back to a small bundled
sample file, so you can start immediately either way.

Nothing you download is committed to git -- see [`data/README.md`](../data/README.md),
which also lists what each file in a deployment contains.

---

## Running a script without a notebook

Not everything has to be a notebook. From a terminal, at the top level of the
repo:

```bash
# Python
python3 aksel_s_example/example.py

# R
Rscript path/to/your_script.R
```

The general shape is `python3 <path to the file>` or `Rscript <path to the file>`.

### Why paths sometimes break

A notebook runs from the folder *it* lives in, not from the top of the repo. So
inside `notebooks/`, the file `data/sample_stations.csv` is not found -- it is
`../data/sample_stations.csv` from there.

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

## Saving your work

Your work is not safe until it is pushed to GitHub. In a terminal:

```bash
git add .
git commit -m "a short note about what you did"
git push
```

The full walkthrough -- forking, cloning, and opening a pull request so your work
reaches the shared repo -- is in the [main README](../README.md).

Two habits worth having:

- **Clear notebook outputs before committing.** A notebook saves its outputs
  inside the file, so simply re-running one shows up as a change. *Kernel >
  Restart Kernel and Clear Outputs* keeps pull requests readable.
- **Keep your work in your own folder**, named `your-name-your-feature`, as the
  README asks. And follow [`code_standards.md`](code_standards.md): every script
  needs a header saying what it is, how to run it, and what goes in and out. In a
  notebook, put that header in the first markdown cell -- notebooks 01-04 show
  the pattern.

---

## Working locally instead of in Binder

If you would rather not use Binder:

```bash
git clone https://github.com/NMFS-PAM-Glider/hackathon-shared-repo.git
cd hackathon-shared-repo

pip install -r binder/requirements.txt
Rscript binder/install.R          # only if you want the R notebooks

jupyter lab
```

You will need Python 3, and R if you want the R notebooks. To run R notebooks
locally you also need the R kernel, which Binder installs for you automatically:

```r
install.packages("IRkernel")
IRkernel::installspec()
```

---

## When something goes wrong

| Symptom | Likely cause |
|---|---|
| `NameError` or `invalid syntax` in an R notebook | Wrong kernel -- check the top-right corner says `R` |
| `FileNotFoundError` / `cannot open file` | Path is relative to `notebooks/`, not the repo root -- see above |
| `ModuleNotFoundError` | Package missing; in Binder this means the image did not build |
| Binder is slow the first time | Normal -- it is building the image; later launches are cached |
| Your downloaded data vanished | Binder session ended; re-run the fetch script |

Still stuck? Open an issue on the repo, or ask an organiser.
