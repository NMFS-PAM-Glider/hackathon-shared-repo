# tutorials/

Longer worked examples contributed by the community, kept separate from the
numbered starter notebooks in [`notebooks/`](../notebooks).

Work through `notebooks/01`–`04` first if you are new here -- they cover the
basics these tutorials assume.

---

## Comparing Glider Observations with Satellite Data

*By Madison Richardson, Cara Wilson & Dale Robinson (NOAA CoastWatch). Updated
September 2026.*

| Language | File | Open it with |
|---|---|---|
| Python | [`GliderTracks_python.ipynb`](GliderTracks_python.ipynb) | JupyterLab, **Python 3** kernel |
| R | [`GliderTracks_r.Rmd`](GliderTracks_r.Rmd) | RStudio (Binder provides it) |

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

It also shows a second route to ERDDAP. Starter notebook 03 reaches ERDDAP
through the AquaView STAC catalogue; these tutorials go directly, using
`erddapy` in Python and `rerddap` in R.

### What it needs

Everything is installed in the Binder image already:

- **Python:** `erddapy`, `xarray`, `netcdf4`, `pydap`, `pandas`, `matplotlib`
- **R:** `rerddap`, `rerddapXtracto`, `tidyverse`, `scales`

The R version also tries to install its own packages in the first chunk. In
Binder they are already there, so that step simply does nothing.

No hackathon data and no credentials are needed -- everything is pulled live from
public ERDDAP servers. You do need an internet connection, and the satellite
matching steps take a few minutes to run.

### Data sources

| What | Server | Dataset |
|---|---|---|
| Glider track | `spraydata.ucsd.edu` | `binnedCUGN90` |
| Chlorophyll-a | `coastwatch.pfeg.noaa.gov` | `pmlEsaCCI60OceanColorDaily` |
| Sea surface temperature | `coastwatch.pfeg.noaa.gov` | `noaacwLEOACSPOSSTL3SCWeeklyNRT` |
| Sea surface salinity (Python) | `coastwatch.noaa.gov` | `noaacwSMOSsss3day` |
| Sea surface salinity (R) | `coastwatch.pfeg.noaa.gov` | `coastwatchSMOSv662SSS3day` |

The two versions use different salinity datasets -- both are SMOS sea surface
salinity, just published on different CoastWatch servers. All five were
confirmed reachable in September 2026.

> If a tutorial fails partway through, an ERDDAP dataset has most likely been
> renamed or retired -- these servers do change. Search the server listed above
> for a current equivalent, or ask an organiser.

---

## Adding your own tutorial

Contributions welcome. Please include:

- Both a Python and an R version where it makes sense, named `*_python.ipynb`
  and `*_r.Rmd` (or `*_r.ipynb`).
- A header describing what it does and how to run it, per
  [`docs/code_standards.md`](../docs/code_standards.md). In a notebook, that goes
  in the first markdown cell.
- Any new packages added to [`binder/requirements.txt`](../binder/requirements.txt)
  or [`binder/install.R`](../binder/install.R), so it runs in Binder.
- A section here saying what it covers and what it needs.
