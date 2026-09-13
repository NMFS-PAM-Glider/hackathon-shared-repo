# R packages for the hackathon environment.
# Binder (repo2docker) runs this automatically when the image is built.
#
# Note: IRkernel (the R kernel for Jupyter) is installed by Binder itself,
# so it must NOT be listed here.

install.packages(c(
  # Used by the starter notebooks in notebooks/
  "jsonlite",       # read JSON from the AquaView STAC API
  "readr",          # read CSV files and URLs
  "dplyr",          # filter / summarise data frames
  "ggplot2",        # plots

  # Used by the tutorials in tutorials/
  "rerddap",        # query ERDDAP servers
  "rerddapXtracto", # match satellite data to a track
  "tidyverse",      # dplyr/ggplot2/tidyr/etc as one bundle
  "scales"          # axis formatting for the tutorial plots
))
