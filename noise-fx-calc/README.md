# PAM-Glider Noise Profiler

## Collaborators
Aaron (Will) Deans | xxx | xxx | xxx   
Julia Engdahl | Rutgers University, Center for Ocean Observing Leadership | engdahl@marine.rutgers.edu   
Liz Ferguson | xxx | xxx | xxx   
Kaitlin Palmer | xxx | xxx | xxx

## Folder Structure
This is a 3-phase approach:   

        1. glider_data_explore.ipynb: Requires glider science data (csv), PAM noise data (h5), and glider mission phase key (xlsx). This notebook merges the dataframes together where time is within a 90s tolerance and applies quality control (pending) utilizing configurations set in config.py and functions from noise_utils.py. Exports the merged science data (csv) and PAM noise spectrum (parquet) to a per-glider `data/` subfolder for the next notebook.    
        2. glider_noise_stats_plots.ipynb: Reads the merged science csv and PAM noise spectrum parquet exported by glider_data_explore.ipynb. Bins the CTD/science variables (temperature, salinity, density, sound velocity, depth) and builds the per-mode and per-bin noise comparison plots (mean spectra, box plots, and correlation tables/matrices), saving figures and result tables to per-glider `figures/` and `data/` subfolders for the presentation notebook.   
        3. glider_noise_presentation.ipynb: Reads the tables and figures produced by glider_noise_stats_plots.ipynb and assembles them into a summary PowerPoint deck for the glider deployment.

Supporting scripts (imported by the notebooks above, not run directly):  

        - config.py: Single place for every setting used across the three notebooks - which glider/deployment to analyze, local vs. JupyterHub paths, output folders, the science/noise merge tolerance, the QC toggle, excluded mission phases, and variable binning widths.   
        - noise_utils.py: Shared helpers for parsing the PAM noise HDF5 files and for the per-mode/per-bin noise analysis (h5 structure inspection, building the noise DataFrame, bin-edge calculation, and the correlation-matrix/spectrum/box plotting functions). ** QC functions will be added here ***   
        - pptx_utils.py: Generic PowerPoint deck-building helpers (title/section/bullet/image slides) used by glider_noise_presentation.ipynb.

## Background

## Goals

## Methods

### Datasets

### Workflow

## Lessons Learned

## Presentation


## References

## Acknowledgements
This project was part of a [Glider Rodeo Hackathon] which worked with (or was inspired by) PAM-Glider data collected by the NOAA Fisheries Glider Rodeo (2026). This weeklong event was hosted by NOAA Fisheries with support by Openscapes (JupyterHub, Support), Oregon State University (Zoom, Box data storage), Aquaview (technical support). 



