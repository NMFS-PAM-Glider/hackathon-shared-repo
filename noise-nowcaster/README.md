# Noise Nowcaster

Predicting hourly ambient noise levels in five whale-call frequency bands from
weather and sea state, and turning those levels into how far a glider can expect
to hear.

- **Code and full results:** https://github.com/imbishal7/GliderRodeo
- **Presentation:** https://storage.googleapis.com/aquaview-public-assets/glider-rodeo/noise-nowcaster-slides.html

This folder is a pointer and a summary rather than a copy of the project. The
repository above is the authoritative version and is still developing, so a copy
placed here would go out of date.

## Collaborators

| Name | GitHub |
|---|---|
| Kapil Sharma | [@imbishal7](https://github.com/imbishal7) |
| Suramya Angdembay | [@SuramyaAngdembay](https://github.com/SuramyaAngdembay) |

*Affiliations and contact addresses still to be added by the authors.*

## Background

How much ocean a passive-acoustic glider is actually monitoring depends on how
loud the background is. Over the Rodeo mission, measured noise in the sperm whale
band moved across roughly 14 dB, which corresponds to about a **23× difference in
monitored area** between a quiet hour and a loud one. If you can say in advance
which hours will be quiet, you can plan a survey around them.

Most of that variation is driven by weather, and weather is forecastable. That is
the opening this project tries to use.

## Goals

1. Predict hourly band levels from environmental conditions alone.
2. Convert predicted levels into detection range and monitored area.
3. Establish whether the predictions hold up on a glider the model has never seen,
   rather than only on more hours of gliders it already knows.

## Methods

### Datasets

| Source | Contribution |
|---|---|
| **AQUAVIEW / PacIOOS** | All environmental inputs — wind, waves, swell, currents, temperature, bathymetry (~80% of model features) |
| **Glider Rodeo hydrophones** | Measured band levels (the labels) plus glider depth and state (~20%) |

6 platforms, 1,565 glider-hours, 5 bands (fin whale 20 Hz, humpback song, sperm
whale clicks, odontocete whistles, beaked whale upsweeps).

The Rodeo detection files are synthetic, so nothing here uses them. The labels are
measured noise levels, which are real.

### Workflow

Environmental fields and acoustic band levels are joined on an hourly grid. Each
target is expressed relative to its own platform's median, because recorders
disagree with one another by considerably more than the signal being predicted.

Scoring is **leave-one-glider-out**: train on five platforms, score on the sixth,
rotate. Forward-in-time and spatial-holdout protocols were also run. Uncertainty
is a paired bootstrap over whole UTC days, since adjacent hours are not
independent samples.

## Lessons Learned

- **Score on a platform you have never seen.** Anything easier flatters the model.
  Several approaches that looked good on held-out hours did nothing on a held-out
  glider.
- **Sea state separates the regimes; location does not.** A two-expert model whose
  gate looks at wind and wave conditions improved unseen-glider error by ~2.8% over
  the project's own earlier model, and reproduced under a second seed. The same
  architecture gated on geography or on bathymetry gained essentially nothing.
- **Different approaches converged on the same floor.** A mixture of experts,
  fine-tuning a pretrained tabular model, and a simple per-platform rescaling all
  landed within a few hundredths of a dB of one another, and combining them did not
  stack. Two of them scored better on paper but did not survive a re-run. Where
  that happens, the simplest reproducible option is the honest one to ship.
- **One band resisted everything.** The fin whale band sits at 10–30 Hz where
  vessel noise dominates, and no AIS data was available for this window. It is the
  weakest band by a wide margin, and the clearest argument for adding vessel traffic
  data next time.
- **Overlapping bands are not independent results.** Sperm whale (5–15 kHz) is a
  strict subset of odontocete (5–20 kHz), and the two measured series correlate at
  r = 0.9997. Reporting both as separate wins counts one result twice.

## Acknowledgements

This project was part of a Glider Rodeo Hackathon which worked with (or was
inspired by) PAM-Glider data collected by the NOAA Fisheries Glider Rodeo (2026).
This weeklong event was hosted by NOAA Fisheries with support by Openscapes
(JupyterHub, Support), Oregon State University (Zoom, Box data storage), Aquaview
(technical support).
