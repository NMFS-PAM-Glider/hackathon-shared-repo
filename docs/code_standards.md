# Code Standards

Each script shall contain a header that has the following:
	- The name of the file.
	- What the file is supposed to do.
	- How to run the file.
	- What inputs the script needs (if any).
	- What outputs the script creates (if any).

## In a notebook

A notebook has no comment header, so put the same information in the **first
markdown cell**. The notebooks in [`notebooks/`](../notebooks) all follow this
pattern:

```markdown
# 01 - Hello World (Python)

**File:** `notebooks/01_hello_world_python.ipynb`

**What this does:** Prints a greeting and confirms the Python environment works.

**How to run it:** Open in JupyterLab, check the kernel says **Python 3**, then
choose *Run > Run All Cells*.

**Inputs:** none

**Outputs:** printed text only
```

Two more things that keep notebooks reviewable:

- **Clear outputs before committing.** *Kernel > Restart Kernel and Clear
  Outputs*. A notebook stores its output inside the file, so re-running one shows
  up as a change even when you edited nothing.
- **Say what a cell is doing** in a short markdown cell above it, rather than
  leaving a wall of code.
