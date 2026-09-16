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

As a platform for passive acoustic monitoring, gliders are remarkably quiet. Nevertheless, they must contend with sources of self-noise (Grasso et al., 2023) and flow noise (Cauchy, 2026; Fregosi et al., 2020). Less-predictable external sources, including wind (Shajahan et al., 2025) and human activity (Hildebrand, 2009), also contribute to the noise recorded by PAM platforms. Noise may limit our ability to acoustically detect marine mammals by lowering signal-to-noise ratios (SNR), reducing probabilities of detection for marine mammal vocalizations (Fregosi et al., 2020).

To evaluate the effect of noise on marine mammal detection, it is helpful to first identify the conditions which yield elevated noise levels. We must determine: What variables (EX. glider mode, depth, location, etc.) affect noise levels, and how? Are these effects broadband (affecting all frequencies) or narrowband (affecting only select frequency bands)? Answering these questions will allow us to identify the times when noise conditions may mask signals of interest. Future work will be able to determine whether these conditions significantly reduce the probability of signal detection.

## Goals
The **Noise Profiler** tool will output a slideshow-based automated report summarizing how noise levels are linked to input variables of interest. The slideshow will include plots characterizing the effect of noise sources that may impact passive acoustic gliders – including mode, depth, location, and environmental variables – on broadband and hybrid-millidecade band levels. These will allow the user to easily visualize which conditions contribute to elevated noise levels, and which frequency bands are most affected.


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
Cauchy, P. (2026). Ocean sound measurements collected from underwater gliders with marginal effects of flow noise. The Journal of the Acoustical Society of America, 160(3), 1936–1947. https://doi.org/10.1121/10.0046395

Fregosi, S., Harris, D. V., Matsumoto, H., Mellinger, D. K., Negretti, C., Moretti, D. J., Martin, S. W., Matsuyama, B., Dugan, P. J., & Klinck, H. (2020). Comparison of fin whale 20 Hz call detections by deep-water mobile autonomous and stationary recorders. The Journal of the Acoustical Society of America, 147(2), 961–977. https://doi.org/10.1121/10.0000617

Grasso, M., Velázquez, L. P., & Van Uffelen, L. (2023). Quantifying Self-Noise of the Seaglider AUV Using a Passive Acoustic Monitor. Marine Technology Society Journal, 57(3), 30–42. https://doi.org/10.4031/MTSJ.57.3.5

Hildebrand, J. A. (2009). Anthropogenic and natural sources of ambient noise in the ocean. Marine Ecology Progress Series, 395, 5–20. https://doi.org/10.3354/meps08353

Shajahan, N., Halliday, W. D., Barclay, D. R., Melling, H., Neimi, A., & Insley, S. J. (2025). Wind-driven ambient noise characteristics in the Western Canadian arctic. JASA Express Letters, 5(2), 026001. https://doi.org/10.1121/10.0035591

## Acknowledgements
This project was part of a [Glider Rodeo Hackathon] which worked with (or was inspired by) PAM-Glider data collected by the NOAA Fisheries Glider Rodeo (2026). This weeklong event was hosted by NOAA Fisheries with support by Openscapes (JupyterHub, Support), Oregon State University (Zoom, Box data storage), Aquaview (technical support). 



