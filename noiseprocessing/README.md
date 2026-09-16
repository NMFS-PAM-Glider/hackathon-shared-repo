# noiseprocessing/

NoiseApp (YAWN) -- the hybrid millidecade noise analysis used by
[`notebooks/07`](../notebooks/07_noise_processing_python.ipynb) and
[`notebooks/08`](../notebooks/08_pypam_validation_python.ipynb).

**This is a vendored copy, not our code.** Do not edit
`noiseProcessGoogleCloud.py` here -- changes belong upstream, or they are lost
the next time it is re-synced.

## Where it came from

| | |
|---|---|
| Upstream | [PIFSC-Protected-Species-Division/SPACIOUS-NoiseProcessing](https://github.com/PIFSC-Protected-Species-Division/SPACIOUS-NoiseProcessing) |
| File | `NoiseProcessing/noiseProcessGoogleCloud.py` |


## Using it

Both of these work:

```python
from noiseprocessing import NoiseApp                 # repo root on sys.path
from noiseProcessGoogleCloud import NoiseApp         # this folder on sys.path
```

The notebooks use the second form, because that is how the upstream examples are
written. They have a short setup cell that puts this folder on `sys.path`, so
their import lines stay identical to upstream.

## What it needs

`h5py`, `scipy`, `seaborn`, `soundfile`, `numpy`, `pandas`, `matplotlib` -- all
in [`requirements.txt`](../requirements.txt). `google-cloud-storage` is optional
and only needed to read audio straight from a `gs://` bucket; without it the
module still imports and works on local files.

## Re-syncing

```bash
curl -sfL https://raw.githubusercontent.com/PIFSC-Protected-Species-Division/SPACIOUS-NoiseProcessing/main/NoiseProcessing/noiseProcessGoogleCloud.py \
  -o noiseprocessing/noiseProcessGoogleCloud.py
```