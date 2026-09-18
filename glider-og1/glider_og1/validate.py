"""
File: glider-og1/glider_og1/validate.py

What it does: Checks an xarray Dataset (or NetCDF path) against the mandatory
    parts of the OG1.0 specification
    (https://oceangliderscommunity.github.io/OG-format-user-manual/OG_Format.html)
    plus a few sanity checks on the data itself. Works on any OG1 file, not only
    ones made by this converter.

How to run: `python glider-og1/check_og1.py <file.nc> [...]`, or call check(ds).

Inputs: an OG1 Dataset or NetCDF file path
Outputs: list of (level, message) tuples; level is ERROR, WARN or INFO
"""

from pathlib import Path

import numpy as np
import xarray as xr

MANDATORY_GLOBALS = ["title", "platform", "platform_vocabulary", "id", "featureType", "Conventions",
                     "start_date", "date_created", "rtqc_method"]
PI_GLOBALS = ["contributor_name", "contributor_email", "contributing_institutions"]
MANDATORY_VARS = ["TIME", "LATITUDE", "LONGITUDE", "DEPTH", "TIME_GPS", "LATITUDE_GPS", "LONGITUDE_GPS",
                  "TRAJECTORY", "WMO_IDENTIFIER", "PLATFORM_MODEL", "PLATFORM_SERIAL_NUMBER",
                  "DEPLOYMENT_TIME", "DEPLOYMENT_LATITUDE", "DEPLOYMENT_LONGITUDE"]
DESIRABLE_VARS = ["PHASE", "PROFILE_NUMBER", "PROFILE_DIRECTION", "SEGMENT_NUMBER", "PLATFORM_NAME"]
DIM = "N_MEASUREMENTS"


def check(ds_or_path):
    path = None
    if isinstance(ds_or_path, (str, Path)):
        path = Path(ds_or_path)
        ds = xr.open_dataset(path)
    else:
        ds = ds_or_path
    out = []
    err = lambda m: out.append(("ERROR", m))  # noqa: E731
    warn = lambda m: out.append(("WARN", m))  # noqa: E731
    info = lambda m: out.append(("INFO", m))  # noqa: E731

    # --- global attributes ---------------------------------------------------
    for a in MANDATORY_GLOBALS:
        if not str(ds.attrs.get(a, "")).strip():
            err(f"missing mandatory global attribute '{a}'")
    for a in PI_GLOBALS:
        if not str(ds.attrs.get(a, "")).strip():
            warn(f"missing global attribute '{a}' (mandatory for PI/operator, fill in the deployment YAML)")
    if ds.attrs.get("featureType") not in (None, "trajectory"):
        err("featureType must be 'trajectory'")
    if "OG-1.0" not in str(ds.attrs.get("Conventions", "")):
        err("Conventions must include 'OG-1.0'")
    if path and ds.attrs.get("id") and path.stem != ds.attrs["id"]:
        warn(f"file name '{path.name}' does not match id '{ds.attrs['id']}.nc'")

    # --- dimensions and variables ---------------------------------------------
    extra_dims = sorted({d for v in ds.variables.values() for d in v.dims} - {DIM})
    if extra_dims:
        err(f"OG1 uses the single dimension {DIM}; found also {extra_dims}")
    for v in MANDATORY_VARS:
        if v not in ds.variables:
            err(f"missing mandatory variable '{v}'")
    for v in DESIRABLE_VARS:
        if v not in ds.variables:
            warn(f"missing highly desirable variable '{v}'")
    if "WMO_IDENTIFIER" in ds and not str(ds.WMO_IDENTIFIER.values).strip():
        warn("WMO_IDENTIFIER is empty")

    sensors = {n for n in ds.variables if str(n).startswith("SENSOR_")}
    for name, var in ds.variables.items():
        if var.ndim == 0 or str(name).endswith("_QC") or name in ("TIME", "TIME_GPS"):
            continue
        if "long_name" not in var.attrs:
            err(f"{name}: missing long_name")
        is_flag = "flag_values" in var.attrs or name in ("PROFILE_NUMBER", "SEGMENT_NUMBER")
        if "units" not in var.attrs and not is_flag:
            err(f"{name}: missing units")
        if "sensor" in var.attrs and var.attrs["sensor"] not in sensors:
            err(f"{name}: sensor '{var.attrs['sensor']}' has no matching SENSOR_* variable")
    for name in sensors:
        for a in ("sensor_type_vocabulary", "sensor_model", "sensor_model_vocabulary"):
            if not str(ds[name].attrs.get(a, "")).strip():
                warn(f"{name}: empty '{a}'")
    for name in [n for n in ds.variables if str(n).endswith("_QC")]:
        if "flag_meanings" not in ds[name].attrs:
            err(f"{name}: missing flag_meanings")

    # --- data sanity -----------------------------------------------------------
    if "TIME" in ds:
        t = ds.TIME.values
        if np.any(np.diff(t.astype("datetime64[ns]").astype("int64")) <= 0):
            err("TIME is not strictly increasing")
    for v, lo, hi in (("LATITUDE", -90, 90), ("LONGITUDE", -180, 180), ("DEPTH", -5, 11000)):
        if v in ds:
            vals = ds[v].values
            out_of_range = (vals < lo) | (vals > hi)
            flagged = ds[f"{v}_QC"].values == 4 if f"{v}_QC" in ds else np.zeros(vals.shape, bool)
            if np.sum(out_of_range & ~flagged):
                err(f"{v}: {np.sum(out_of_range & ~flagged)} values outside [{lo}, {hi}] not flagged bad in {v}_QC")
            if np.sum(out_of_range & flagged):
                info(f"{v}: {np.sum(out_of_range & flagged)} out-of-range values flagged bad in {v}_QC")
            missing = float(np.mean(np.isnan(vals))) * 100
            (warn if missing > 5 else info)(f"{v}: {missing:.1f}% of rows missing")
    if "PHASE" in ds:
        # OG1 uses 0 (unknown) as the PHASE fill value, so it reads back as NaN
        counts = dict(zip(*np.unique(np.nan_to_num(ds.PHASE.values, nan=0).astype(int), return_counts=True)))
        meanings = dict(zip(ds.PHASE.attrs.get("flag_values", []), ds.PHASE.attrs.get("flag_meanings", "").split()))
        info("PHASE share: " + ", ".join(f"{meanings.get(k, k)} {100 * c / ds.sizes[DIM]:.1f}%"
                                         for k, c in sorted(counts.items())))
    if "PROFILE_NUMBER" in ds:
        info(f"profiles: {int(np.nanmax(ds.PROFILE_NUMBER.values))}")
    return out


def summarize(results):
    errors = sum(1 for level, _ in results if level == "ERROR")
    warnings = sum(1 for level, _ in results if level == "WARN")
    lines = [f"  {level:5} {msg}" for level, msg in results]
    lines.append(f"  -> {'PASS' if not errors else 'FAIL'}: {errors} errors, {warnings} warnings")
    return "\n".join(lines)
