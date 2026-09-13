# R packages used by this repo.
#
#   Rscript install.R

install.packages(c(
  # Used by the starter notebooks in notebooks/
  "jsonlite",       # read JSON from the AquaView STAC API
  "ggplot2",        # plots

  # Used by notebook 04
  "rerddap",        # query ERDDAP servers
  "rerddapXtracto", # match satellite data to a track
  "tidyverse",      # dplyr/ggplot2/readr/tidyr etc as one bundle
  "scales",         # axis formatting for the tutorial plots

  # The R kernel for Jupyter. After installing, register it with:
  #   IRkernel::installspec()
  "IRkernel"
))
