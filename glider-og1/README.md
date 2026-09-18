# glider-og1: Glider Rodeo data in OceanGliders OG1.0 format

Converts the per-glider CSV exports from the Glider Rodeo into standard
[OceanGliders OG1.0](https://oceangliderscommunity.github.io/OG-format-user-manual/OG_Format.html)
NetCDF files, so analysis tools can be written once against one format and work for
every glider type, including future deployments.

```
 Glider CSVs (different per manufacturer)     one reader per platform       one OG1 file per deployment
 ───────────────────────────────────────  →  ───────────────────────  →  ─────────────────────────────  →  analysis tools
 Slocum m_* (radians, S/m)                    readers/slocum.py            TIME, LATITUDE, LONGITUDE,        (read OG1 only)
 Seaglider agate (degrees, cm/s)              readers/seaglider.py         DEPTH, PHASE, PROFILE_NUMBER,
 SeaExplorer (NavState, mS/cm)                readers/seaexplorer.py       GLIDER_PITCH, TEMP, ...
 Oceanscout (CTD only)                        readers/oceanscout.py
                                              + deployments/*.yaml
```

## Collaborators
Ehsan Abdi, Akvaplan-niva, eab@akvaplan.niva.no

## Folder structure
```
glider-og1/
├── convert.py              entry point: CSVs -> OG1 NetCDF (+ compliance report)
├── check_og1.py            run the OG1 compliance checker on any .nc file
├── requirements.txt
├── deployments/            one YAML per deployment: reader, input files, platform/sensor metadata
│   └── _common.yaml        global attributes shared by all rodeo deployments
└── glider_og1/
    ├── variables.py        registry of every output variable: OG1 name, units, attributes
    ├── readers/            one module per platform/file layout
    ├── derive.py           positions, depth, PHASE / PROFILE_NUMBER (same method for all gliders)
    ├── build.py            assemble and write the OG1 Dataset
    └── validate.py         OG1 compliance + sanity checks
```

## Quick start

Run from the repository root with the repo's Python environment.

On JupyterHub, straight from the shared data:
```bash
pip install -r glider-og1/requirements.txt
python glider-og1/convert.py --data-dir ~/shared-public/GliderRodeo --out-dir ~/og1 --all
```

Locally, after copying deployment folders into `data/` (gitignored):
```bash
python glider-og1/convert.py --data-dir data --out-dir data/og1 --all
python glider-og1/check_og1.py data/og1/*.nc
```
All seven deployments convert in about 30 s; the largest (capex987, 1.4 million rows) peaks at about 1 GB of memory.

Use the output:
```python
import xarray as xr
ds = xr.open_dataset("data/og1/sg607_20260128T221624_delayed.nc")
dives = ds.where(ds.PROFILE_DIRECTION == 1, drop=True)   # descending rows only
```
The files also open in [glider-playground](https://github.com/Orlando-PB/glider-playground)
(`GP_DATA_DIR=data/og1 glider-playground`) and work with
[glidertest](https://github.com/OceanGlidersCommunity/glidertest).

## Converted deployments

| Deployment | Glider | Reader | Output file | Rows | Profiles | Reference check |
|---|---|---|---|---|---|---|
| stenella-20260128 | Slocum G3S | slocum | `unit_1031_20260128T204716_delayed.nc` | 300,776 | 230 | 223 native profiles deeper than 20 m; direction agrees on 95.5% of rows |
| risso-20260128 | Slocum G3S | slocum | `unit_1025_20260128T235532_delayed.nc` | 309,958 | 203 | all 195 native profiles matched while engineering data exists; 95.2% direction agreement |
| capex987-20260128 | Slocum G3S | slocum | `unit_987_20260129T005504_delayed.nc` | 1,399,259 | 235 | 173 of 176 native profiles matched; 95.7% direction agreement |
| sg607_20260128 | Seaglider M1 | seaglider | `sg607_20260128T221624_delayed.nc` | 128,519 | 130 | 65 dives × 2; dz/dt matches the flight model (median difference 0.0006 m/s) |
| sg274_20260128 | Seaglider SGX | seaglider | `sg274_20260129T003322_delayed.nc` | 195,952 | 139 | 70 dives in the GPS file (140 profiles) |
| SEA117-M026_20260128 | SeaExplorer | seaexplorer | `sea117_20260128T214000_delayed.nc` | 595,336 | 179 | 88 yos (176 profiles); direction agrees with NavState on 99.9% of descent/ascent rows |
| belladonna_20260128 | Oceanscout | oceanscout | `belladonna_20260128T230144_delayed.nc` | 502,762 | 254 | exactly one profile per dive with CTD data (254) |

All seven pass the OG1 checker with 0 errors. Remaining warnings are metadata not in the rodeo
data: contributor name/email (filled only for capex987 and SEA117, from their source YAMLs),
WMO ids, and some CTD model/serial numbers (marked TODO in the YAMLs). Confirm them with the data
owners before sharing files outside the hackathon.

## What goes into each file

| OG1 variable | Slocum | Seaglider | SeaExplorer | Oceanscout |
|---|---|---|---|---|
| `TIME` | `time_utc` | `time` | `Time` | `time` |
| `LATITUDE`, `LONGITUDE` | interpolated between GPS fixes and science positions | GPS fixes + dead-reckoned science positions | GPS file + dead-reckoned file | GPS fixes + science positions |
| `*_GPS` | `m_gps_lat/lon` | dive start/end fixes | GPS file | GPS file |
| `DEPTH` | science `depth`, else `m_depth` | science `depth` | `Depth` (navigation sensor) | `depth_m` |
| CTD | `PRES TEMP CNDC PSAL DENSITY THETA POTDENS` | `TEMP PSAL DENSITY SOUNDVEL` | `PRES TEMP CNDC PSAL TEMP_CNDC SOUNDVEL POTDENS` | `PRES TEMP CNDC PSAL DENSITY SOUNDVEL` |
| attitude | `GLIDER_PITCH/ROLL/HEADING` (from radians) | `GLIDER_PITCH/ROLL/HEADING` | `GLIDER_PITCH/ROLL/HEADING`, `GLIDER_HEADING_COMMANDED` | none |
| buoyancy | `OIL_VOL`, `OIL_VOL_COMMANDED` | `GLIDER_RELATIVE_VBD` | `BALLAST_POSITION`, `BALLAST_COMMANDED` | none |
| flight | `GLIDER_SPEED(_AVG)`, `FIN_ANGLE(_COMMANDED)`, `GLIDER_PITCH_COMMANDED`, `GLIDER_PITCH_MASS_POSITION` | `GLIDER_*_VELO_MODEL`, `GLIDE_ANGLE_MODEL`, `BUOYANCY_MODEL` | `PITCH_MOTOR_*`, `ROLL_MOTOR_*`, `NAV_STATE` | none |
| energy / storage | `BATTERY_VOLTAGE`, `BATTERY_CURRENT`, `BATTERY_CHARGE_USED(_TOTAL)` | none | `BATTERY_VOLTAGE`, `STORAGE_USED(_SSD)`, `INTERNAL_PRESSURE/TEMPERATURE` | none |
| currents | none | `WATERCURRENTS_U/V` (per dive) | none | none |
| derived, all gliders | `PHASE`, `PROFILE_DIRECTION`, `PROFILE_NUMBER`, `SEGMENT_NUMBER`, `DEPTH_Z`, `GLIDER_VERT_VELO_DZDT` | same | same | same |

Every variable records its `source_column` and `source_file`. Variables in the
OG1 vocabulary carry a `vocabulary` link; engineering variables that OG1 does not
define yet have none. Hydrophones are listed as `SENSOR_HYDROPHONE_<serial>` variables
(recorder, sensitivity) to support the noise work.

## Design decisions
- **One method for every glider.** `PHASE` and profiles are derived from the depth record in
  `derive.py`, not from each manufacturer's state flags, so "descent" means the same on every
  platform. Thresholds are in `derive.DEFAULTS` and can be overridden per deployment under
  `derive:` in its YAML. Same-direction pieces separated by a data gap are one profile only if the
  gap is under 300 s and the smoothed depth carries on; this keeps dives with short gaps whole and
  still separates back-to-back dives whose climb was not sampled. Drift periods (`PHASE` = parking)
  split a dive into two profiles.
- **No resampling.** Streams are merged on their own timestamps, and a row is NaN for
  variables not sampled at that time. Only the coordinates are interpolated onto every row.
- **`PROFILE_NUMBER` on every row.** Rows between profiles keep the preceding number, matching
  the OceanGliders example files glidertest is built on. Use `PROFILE_DIRECTION != 0` to select
  only the ascending/descending parts.
- **`PROFILE_DIRECTION` has no fill value.** The spec's `_FillValue = 0` would turn "not
  profiling" into NaN on read, and `PROFILE_DIRECTION != 0` would then match those rows too.
- **Minimal QC.** All `*_QC` flags are 0 (no QC performed), except `DEPTH_QC = 4` where
  `DEPTH < -2 m`. The source data are marked PRELIMINARY.
- **Isolated bad GPS fixes are dropped**: a fix is removed when getting to it and leaving it would
  both need more than 10 m/s.
- **float32** for measured variables (float64 for time and coordinates) keeps memory and file size down.

## Adding a glider
1. **Same layout as an existing platform:** copy a YAML in `deployments/`, change
   `source_folder`, the `files` patterns and the platform/sensor block.
2. **New file layout or platform:** add `glider_og1/readers/<name>.py` with a
   `read(folder, files)` function that maps columns to names in `variables.py` and
   returns a `GliderData`, then register it in `readers/__init__.py`. If you need a new
   variable, add it to `variables.py`; the converter refuses unregistered names.
3. Run `convert.py`; it prints the compliance report.

## Known data issues
Found while converting. These are properties of the source files, not converter changes.
- **risso CTD clock:** CTD depth reads about 3.5 m deeper than the flight computer's depth, and
  the difference mostly disappears if the CTD time is shifted by 15-30 s. The CTD clock is likely
  offset. Not corrected; `DEPTH` mixes both sensors, so it jitters by a few metres between rows.
- **risso and capex987 engineering data end on Feb 10 09:44**, while their CTD files continue
  to Feb 12. After that there are no pitch/battery values and only CTD-sampled profiles.
- **stenella CTD** sampled only a few hours per day, so 26 of 230 profiles have temperature/salinity.
- **Belladonna** has no engineering export. Its CTD records on descents only (no ascent rows),
  its timestamps arrive in bursts (samples < 1 ms apart, then gaps), one GPS fix is corrupt
  (39.4° N, dropped), and the source field definitions swap the latitude/longitude descriptions.
- **SEA117:** `Depth` reads down to -8.6 m for 9 minutes on Jan 28 (flagged in `DEPTH_QC`).
  `PressureNav`/`PressureRel` are in bar although documented as dbar (not converted), humidity is
  always -999 and the altimeter unused. The engineering file is not in time order.
- **Seaglider exports** have no pressure or conductivity columns.

## References
- OG1.0 format manual: https://oceangliderscommunity.github.io/OG-format-user-manual/OG_Format.html
- OG1 parameter vocabulary: https://vocab.nerc.ac.uk/collection/OG1/current/
- glidertest: https://github.com/OceanGlidersCommunity/glidertest
- glider-playground: https://github.com/Orlando-PB/glider-playground
- Related converters for raw files: seagliderOG1 (Seaglider basestation), pyglider (Slocum/SeaExplorer)

## Acknowledgements
This project was part of a [Glider Rodeo Hackathon] which worked with (or was inspired by) PAM-Glider data collected by the NOAA Fisheries Glider Rodeo (2026). This weeklong event was hosted by NOAA Fisheries with support by Openscapes (JupyterHub, Support), Oregon State University (Zoom, Box data storage), Aquaview (technical support).
