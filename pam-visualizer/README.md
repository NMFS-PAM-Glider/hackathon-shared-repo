# PAM Transformer Visualizer

A `streamlit` application for loading Passive Acoustic Monitoring (PAM) and Long-Term Spectral Average (LSTA) data and exploring different filtering techniques on the data.

## Collaborators

| Name | Institution | Email | Other |
|------|-------------|-------|-------|
| Ivia Closset | Finnish Meteorological Institute | ivia.closset@fmi.fi | |
| Brijonnay Madrigal | University of California, San Diego | brmadrigal@ucsd.edu | |
| Aaron Mau | Voice of the Ocean Foundation | aaron.mau@voiceoftheocean.org | No PAM experience! |

## Folder Structure

## Background

This project originated from a common desire to explore the data processing aspects of PAM data. What is typically done when going from the raw file to the final product? How do these different filters modify the data, especially when compared with one another? Furthermore, what are the best ways to visualize these changes?

This grew when the project was proposed - hearing feedback that it would be helpful in the classroom and for new PAM data analysts alike fueled our group's desire to produce something that could be used as a learning tool for others - not just our own.

## Goals

* Build a tool that can load some of the audio data from the PAM rodeo.
* Enable the user to pick from a list of methods that transform or modify the data, and visualize the pre-post changes.
* Load up the LTSA values provided by the hackathon organizers - such that the spectrograms can be compared to the source.
* List the data, with multiple channels if they are supported, such that the transformed values can be downloaded.

## Methods

* `passthrough` - nothing is done. The residual before and after will be 0 (when looking at magnitude - this is set to -200 dB to prevent log errors)
* `lowpass` - a simple Butterworth IIR filter, where the high frequencies are thrown out
* `highpass` - the opposite of a low-pass filter, where the low frequencies are thrown out
* `bandpass` - a combination of the high- and low-pass filters, keeping a band of frequencies
* `notch` - the opposite of a bandpass, removing a "notch" of frequencies of a specified width
* `moving_average` - taking the average of nearby points and then moving forward with a specified window size
* `normalize` - modify the amplitudes to maximum peak size
* `envelope` - Apply a Hilbert transform to estimate "envelopes" of repeating oscillations, combining multiple small signals together
* `downsample` - reduce the number of samples
* `fft` - filtering frequencies and breaking into sinusoidal components
* `PSD (Welch)` - similar to fft, but by averaging the spectrum from various chunks

Meanwhile, data are visualized in 4 ways:
* `Waveform`. Amplitude on the Y axis, time on the X.
* `Spectrum`. Magnitude on the Y axis, frequency on the X.
* `Spectrogram`. Frequency on the Y axis, time on the X, magnitude on the Z. In the spectrogram viewer mode, there is functionality to listen to the visualized sound.
* `Long term spectral average`. Frequency on the Y axis, time on the X (days), magnitude on the Z.


### Datasets

A subset of data collected from gliders in the Baltic Sea was provided by Ivia Closset to test the visualization tool. 

### Workflow

## Lessons Learned


## Next Steps

* `Glider Data`. Does the upcast appear different than the downcast? What about individual glifer states? Need to look at more data.
* `Documentation`. Generate more documentation to assess scientific validity of the methods, create a more detailed notebook for the classroom and initiate a literature review.

## Presentation
Glider rodeo presentation can be found here: https://docs.google.com/presentation/d/1EysKwb2PTtAja1eO1xwhGM8LsgoKEaPa4V8nB1p2CXc/edit?usp=sharing

## Next Steps



## References

We used the assistance of Claude AI for this project.

## Acknowledgements
This project was part of a [Glider Rodeo Hackathon] which worked with (or was inspired by) PAM-Glider data collected by the NOAA Fisheries Glider Rodeo (2026). This weeklong event was hosted by NOAA Fisheries with support by Openscapes (JupyterHub, Support), Oregon State University (Zoom, Box data storage), Aquaview (technical support). 



