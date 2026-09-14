# notebooks/

Worked examples, in order. Each exists twice -- once for Python, once for R -- so
pick whichever language you prefer, or read both to compare.

| # | Topic | Python | R | Needs internet? |
|---|---|---|---|---|
| 01 | Hello world -- check your setup works | `01_hello_world_python.ipynb` | `01_hello_world_r.ipynb` | No |
| 02 | Files and GitHub -- write, read, commit | `02_files_and_github_python.ipynb` | `02_files_and_github_r.ipynb` | No |
| 03 | AquaView -- pull real ocean data from a public catalogue | `03_aquaview_stac_python.ipynb` | `03_aquaview_stac_r.ipynb` | Yes |
| 04 | Glider vs satellite -- a full real-world workflow | `04_glider_satellite_python.ipynb` | `04_glider_satellite_r.ipynb` | Yes |
| 05 | The hackathon data -- list the folder and open a file | `05_hackathon_data_python.ipynb` | `05_hackathon_data_r.ipynb` | No |
| 06 | **AQUAVIEW workshop** -- follow along during the session | `06_aquaview_discovery_python.ipynb` | `06_aquaview_discovery_r.ipynb` | Yes |

Start at 01 even if you have used Python or R before -- it takes a minute and
confirms your environment is set up correctly.

**Check the kernel** in the top-right corner of an open notebook: `_python`
notebooks need `Python 3`, `_r` notebooks need `R`. Getting this wrong is the
most common source of confusing errors. See
[`docs/getting_started.md`](../docs/getting_started.md).

---

## 04 -- Comparing Glider Observations with Satellite Data

*By Madison Richardson, Cara Wilson & Dale Robinson (NOAA CoastWatch). Updated
September 2026.*

### What it does

Takes a real glider track and asks: **does what the glider measured in the water
match what the satellite saw from orbit?**

1. Downloads glider observations along **CalCOFI Line 90** (January–June 2026)
   from the Scripps Spray Glider ERDDAP server.
2. Keeps only near-surface observations (10 m depth), since that is what a
   satellite can see.
3. For each point on the track, pulls the matching satellite measurement from
   NOAA CoastWatch ERDDAP -- matched in both space and time.
4. Plots the two side by side for chlorophyll-a, sea surface temperature and
   sea surface salinity.

### Why it is worth reading

It is a complete, realistic workflow: remote data access, subsetting gridded
data, matching two datasets on space and time, then presenting the comparison.
The space-and-time matching step is the genuinely tricky part, and both versions
show a working approach to it.

It also shows a second route to ERDDAP. Notebook 03 reaches ERDDAP through the
AquaView STAC catalogue; this one goes directly, using `erddapy` in Python and
`rerddap` in R.

### What it needs

Covered by the repo's dependency files:

- **Python:** `erddapy`, `xarray`, `netcdf4`, `pydap`, `pandas`, `matplotlib`
  -- see [`requirements.txt`](../requirements.txt)
- **R:** `rerddap`, `rerddapXtracto`, `tidyverse`, `scales`
  -- see [`install.R`](../install.R)

The R version also tries to install its own packages in its first chunk. If you
have already run `Rscript install.R`, that step finds them and does nothing.

Everything is pulled live from public ERDDAP servers, so you need an internet
connection but no accounts or credentials. The satellite matching steps take a
few minutes to run.

### Data sources

| What | Server | Dataset |
|---|---|---|
| Glider track | `spraydata.ucsd.edu` | `binnedCUGN90` |
| Chlorophyll-a | `coastwatch.pfeg.noaa.gov` | `pmlEsaCCI60OceanColorDaily` |
| Sea surface temperature | `coastwatch.pfeg.noaa.gov` | `noaacwLEOACSPOSSTL3SCWeeklyNRT` |
| Sea surface salinity (Python) | `coastwatch.noaa.gov` | `noaacwSMOSsss3day` |
| Sea surface salinity (R) | `coastwatch.pfeg.noaa.gov` | `coastwatchSMOSv662SSS3day` |

The two versions use different salinity datasets -- both are SMOS sea surface
salinity, just published on different CoastWatch servers. All five were confirmed
reachable in September 2026.

> If it fails partway through, an ERDDAP dataset has most likely been renamed or
> retired -- these servers do change. Search the server listed above for a current
> equivalent, or ask an organiser.

---

## 05 -- The hackathon data

The Glider Rodeo data is not in this repository -- the files are far too big for
git. It lives in a shared folder, and notebook 05 opens it.

### Pointing it at the data

There is one line to change, at the top of the notebook:

```python
DATA = Path.home() / "shared-public" / "GliderRodeo"      # Python
```

```r
data_dir <- file.path(path.expand("~"), "shared-public", "GliderRodeo")   # R
```

If the folder is not there, the notebook says so and stops -- it will not throw a
confusing error. Edit that line to wherever your copy lives and re-run.

### What is in the folder

One folder per glider deployment from January 2026:

`belladonna_20260128`, `capex987_20260128`, `risso_20260128`,
`SEA117-M026_20260128`, `sg274_20260128`, `sg607_20260128`,
`stenella_20260128`

plus a `Noise` folder of raw acoustic `.h5` files, and a few files that apply
across all deployments: `PAM_Glider_Specs.csv` (which hydrophone and platform
each glider carried), `waypoints.csv`, and the Slocum event logs.

A deployment folder typically holds:

| File | |
|---|---|
| `*_fieldDefinitions.csv` | What every column means -- **read this first** |
| `*_GPS_timeseries.csv` | Surface positions. Small, a good place to start |
| `*_science_timeseries.csv` | CTD and science sensors. **Large** |
| `*_flight_timeseries_engineering.csv` | Flight and engineering data. **Large** |
| `*_FakeData_EventDetections.csv`, `*_HrlyDetections.csv` | Acoustic detections |
| `README.html` | Notes from the deployment |

### Watch your memory

The two files marked large run to hundreds of megabytes, and a CSV needs several
times its size in memory to load. Opening one whole can kill your kernel. Read
only the columns you need:

```python
pd.read_csv(path, usecols=["time", "depth", "temperature"])
```

Start from the small files and scale up once your code works.

---

## 06 -- AQUAVIEW workshop

**These are the notebooks for the live AQUAVIEW session.** Open the one for your
language and follow along as the session runs -- you do not need to have read it
beforehand. They work just as well on your own afterwards, if you miss the
session or want a second pass.

Unlike 01-05, which build on each other, these stand alone. Where notebook 03
shows the mechanics of a single STAC request, these are about **finding things**:
one catalogue over 600,000+ datasets from ~90 sources, and how to get at them
without knowing any dataset IDs up front.

The session covers searching a place and time window, narrowing a broad result
to the sources you actually want, comparing what each source holds, and
inspecting a single dataset down to its assets -- worked through on the Hawai'i
box, so it lines up with the Glider Rodeo area.

They use a proper STAC client rather than raw HTTP: `pystac-client` in Python and
`rstac` in R, both installed by the repo's dependency files. Everything runs live
against the public catalogue -- no accounts or keys.

---

## Adding your own

Contributions welcome. Please include:

- Both a Python and an R version where it makes sense, named `*_python.ipynb`
  and `*_r.ipynb`, with the next number in the sequence.
- A header describing what it does and how to run it, per
  [`docs/code_standards.md`](../docs/code_standards.md). In a notebook, that goes
  in the first markdown cell.
- Any new packages added to [`requirements.txt`](../requirements.txt) or
  [`install.R`](../install.R), so others can run it.
- A row in the table above.
