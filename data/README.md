# data/

This folder holds the hackathon dataset.

## What is in here

| File | Committed to git? | Where it comes from |
|---|---|---|
| `sample_stations.csv` | Yes | A tiny 10-row example file, so the notebooks have something to read before you download anything. |
| everything else | **No** | Downloaded by you, from the public hackathon bucket. |

## The dataset

The **Glider Rodeo** collection lives in a public Google Cloud Storage bucket,
`gs://glider-rodeo-data`. No Google account or credentials are needed.

It holds eight glider deployments from January 2026 -- 1.3 GB in total:

| Deployment | Size | |
|---|---|---|
| `capex987_20260128` | 336 MB | Slocum |
| `stenella_20260128` | 104 MB | Slocum |
| `risso_20260128` | 101 MB | Slocum |
| `belladonna_20260128` | 94 MB | Scout |
| `SEA117-M026_20260128` | 86 MB | SeaExplorer |
| `sg607_20260128` | 40 MB | Seaglider |
| `sg274_20260128` | 31 MB | Seaglider |
| `noise data` | 537 MB | Raw acoustic `.h5` files |

Each deployment folder typically contains:

- `*_science_timeseries.csv` -- CTD and science sensor measurements
- `*_flight_timeseries_engineering.csv` -- glider flight and engineering data
- `*_GPS_timeseries.csv` -- surface GPS positions
- `*_FakeData_EventDetections.csv` / `*_HrlyDetections.csv` -- acoustic detections
- `*_fieldDefinitions.csv` -- what each column means (read this first)
- `README.html` -- notes from the deployment

At the top level there are also `PAM_Glider_Specs.csv` (the hydrophone and
platform for each glider), `waypoints.csv`, and the Slocum event logs.

## How to fill this folder

From the top level of the repo, see what is available:

```bash
python3 scripts/fetch_hackathon_data.py
```

Then download one deployment -- start small rather than pulling all 1.3 GB:

```bash
python3 scripts/fetch_hackathon_data.py sg274_20260128
```

Or grab everything:

```bash
python3 scripts/fetch_hackathon_data.py --all
```

Running it again is safe and fast: files you already have are skipped. The
folder layout here mirrors the layout inside the bucket.

## Why is the data not in git?

Research datasets are big, and GitHub rejects files over 100 MB -- several files
here are well over that. Keeping the data out of git means cloning stays fast and
nobody accidentally commits a gigabyte.

The rules that do this live in [`.gitignore`](../.gitignore) at the top of the
repo. `git status` will not show the files you download here, which is the
intended behaviour -- you do not need to do anything about it.

## A warning about Binder

A Binder session is erased when you close it, and anything you downloaded goes
with it. Pulling a single deployment in Binder is fine; for sustained work with
the full dataset, use a local clone or a persistent JupyterHub.
