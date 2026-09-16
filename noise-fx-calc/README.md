# PAM-Glider Noise Profiler

## Collaborators
Aaron Deans | Scripps Institution of Oceanography, Machine Listening Lab | wadeans@ucsd.edu   
Julia Engdahl | Rutgers University, Center for Ocean Observing Leadership | engdahl@marine.rutgers.edu   
Liz Ferguson | Ocean Science Analytics | eferguson@oceanscienceanalytics.com   
Kaitlin Palmer | Contractor with OAI on behalf of NOAA Pacific Islands Fisheries Science Center | kaitlin.palmer@noaa.gov

## Folder Structure
This is a 3-phase approach:


1. glider_data_explore.ipynb: Requires glider science data (csv), PAM noise data (h5), and glider mission phase key (xlsx). This notebook merges the dataframes together where time is within a 90s tolerance and always computes `depth_mask_flag`, a per-row QC flag (see `noise_utils.compute_depth_mask_flag`) - it does not drop any rows itself, so the full flagged dataset is always available downstream. Exports the merged science data (csv, including the flag) and PAM noise spectrum (parquet) to a per-glider `data/` subfolder for the next notebook.
     
3. glider_noise_stats_plots.ipynb: Reads the merged science csv and PAM noise spectrum parquet exported by glider_data_explore.ipynb. When `config.QC_APPLIED` is `True`, drops `depth_mask_flag`-flagged rows from its working copy before analysis (an unfiltered copy is kept for the QC map so flagged points are still visible either way). Bins the CTD/science variables (temperature, salinity, density, sound velocity, depth, latitude, longitude) and builds the per-mode and per-bin noise comparison plots (mean spectra, box plots, correlation tables/matrices, a cartopy glider-track map with a phase-colored panel and a QC-flag panel, and a before-vs-after-QC broadband box plot with a matching per-mode impact table showing rows dropped and the shift in mean SPL), saving figures and result tables to per-glider `figures/` and `data/` subfolders for the presentation notebook.
   
5. glider_noise_presentation.ipynb: Reads the tables and figures produced by glider_noise_stats_plots.ipynb and assembles them into a summary PowerPoint deck for the glider deployment, with the title slide noting whether QC was applied.

Supporting scripts (imported by the notebooks above, not run directly):  

- config.py: Single place for every setting used across the three notebooks - which glider/deployment to analyze, local vs. JupyterHub paths, output folders, the science/noise merge tolerance, the QC toggle, excluded mission phases, and variable binning widths.
  
- noise_utils.py: Shared helpers for parsing the PAM noise HDF5 files and for the per-mode/per-bin noise analysis: h5 structure inspection, building the noise DataFrame, the `depth_mask_flag` QC check, bin-edge calculation, the correlation-matrix/spectrum/box plotting functions, and the cartopy map-axis setup used by the glider-track plot.
  
- pptx_utils.py: Generic PowerPoint deck-building helpers (title/section/bullet/image slides) used by glider_noise_presentation.ipynb.

## Background

## Goals

## Methods

### Datasets
Data come from the NOAA Fisheries **PAM-Glider Rodeo** project ([site](https://nmfs-pam-glider.github.io/GliderRodeo/), [hardware overview](https://nmfs-pam-glider.github.io/GliderRodeo/content/hardware.html)), which is testing passive acoustic monitoring across multiple glider platforms and PAM sensor packages:

| Glider platform | Manufacturer | PAM sensor(s) |
|---|---|---|
| Slocum Glider | Teledyne Webb | DMON, WISPR, OceanObserver |
| Seaglider | U. Washington / OSU | WISPR |
| Oceanscout | Hefring | — |
| SeaExplorer | Alseamar | Auris |

For this workflow, development and testing used a single deployment (Seaglider **SG607**) during the Rodeo deployment window as a proof of concept, with the pipeline written so that additional deployments can be substituted in.

**Audio-derived variable**
- **Hybrid millidecade (HMD) sound levels** — a compressed, standardized representation of the acoustic spectrum often used for sharing long-term soundscape data. Stored as HDF5, generated upstream by an existing PAM processing pipeline. 
- **Sound Pressure Levels (SPL)** - broadband measurements of average acoustic energy, binned in a variable of ways by instrument and environmental variables. 

**Instrument variables**
- **Glider mode** (e.g., dive, climb, drift) from glider mission/flight data
- **Glider depth**, binned in 100-m increments

**Environmental variables**
Binned environmental values were derived from on-board CTD instrumentation and include:
- **Temperature**: 10 degree C temperature bins
- **Salinity**: 0.5 ppt bins
- **Seawater Density**: 2 kg/m³ bins
- **Sound Velocity**: 5 meters per second (m/s) bins

**Data availability**
- Raw PAM data (FLAC/WAV) are not yet available for this workflow (as of 9/15/2026)
- Processed HMD/noise data are available in this repository
- Glider flight and environmental (science) data are available; NetCDF versions grouped by dive/profile via ERDDAP are also in progress


### Workflow
The core workflow proceeds as follows:

1. **Inputs**
   - HDF5 hybrid millidecade levels and SPL values
   - Glider depth, mode, and environmental data — CTD-derived sound speed, etc. 

2. **Build a timetable**
   Align glider mode, depth, and local sound speed to each HMD timestamp, producing a single reference table keyed on time. The timetable is written so additional variables can be appended without changing downstream steps.

3. **Subset the data using the timetable**
   The HMD dataset is split into subsets along each predictor of interest:
   - One subset per **glider mode**
   - One subset per **glider depth bin** (100 m)
   - One subset per **local sound speed bin** (5 m/s)
   - Extends to all environmental variables, binned as described above.
     
4. **Plot each subset**
   For each predictor, generate a hybrid millidecade plot with curves color-coded by that predictor's bin/category (mode, depth bin, or sound speed bin). Plotting resolution (hybrid millidecade / broadband SPL) can be modified.

5. **Output**
   Compile the subset plots into an automated report (PPT, with PDF export). The reporting step uses `python-pptx`, driven by a dictionary mapping report sections to the figures/variables that populate them, so the report regenerates automatically as new deployments or predictors are added.


## Lessons Learned & Future Directions
Quality assessment of instrument noise proved tractable by examining audio characteristics against instrument and environmental features, offering a rapid way to flag regions of poor data quality. Leveraging cloud-based access to data through JupyterHub-formatted code further streamlined this critical first QA/QC step.

We recommend extending the noise assessment to SPL by third-octave band, including bands linked to specific noise sources (e.g., flow noise), for finer diagnostic resolution. We also aim to incorporate bathymetric features into the summative analysis for each recorder.

## Presentation


## References

## Acknowledgements
This project was part of a [Glider Rodeo Hackathon] which worked with (or was inspired by) PAM-Glider data collected by the NOAA Fisheries Glider Rodeo (2026). This weeklong event was hosted by NOAA Fisheries with support by Openscapes (JupyterHub, Support), Oregon State University (Zoom, Box data storage), Aquaview (technical support). 



