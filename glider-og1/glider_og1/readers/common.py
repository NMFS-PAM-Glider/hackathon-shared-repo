"""
File: glider-og1/glider_og1/readers/common.py

What it does: Helpers shared by every platform reader: finding input files by
    pattern, parsing timestamps, applying a column mapping with unit
    conversions, and merging several timeseries on time.

How to run: imported by the platform readers, not run directly.

Inputs: none
Outputs: none

Every reader returns a GliderData:
    data       one row per timestamp; column TIME (datetime64) plus registry names
    positions  TIME, LATITUDE, LONGITUDE from any dead-reckoned/interpolated source
    gps        TIME, LATITUDE_GPS, LONGITUDE_GPS (true surface fixes)
    sources    list of input file paths, recorded in the output's history
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

RAD2DEG = np.degrees(1.0)


@dataclass
class GliderData:
    data: pd.DataFrame
    positions: pd.DataFrame
    gps: pd.DataFrame
    sources: list = field(default_factory=list)
    # extra per-variable attributes, e.g. {"GLIDER_PITCH": {"source_column": "m_pitch"}}
    var_attrs: dict = field(default_factory=dict)


def find_file(folder, pattern, required=True):
    """Return the single file in `folder` matching glob `pattern` (checkpoint copies ignored)."""
    matches = sorted(p for p in Path(folder).glob(pattern) if ".ipynb_checkpoints" not in p.parts)
    if len(matches) > 1:
        raise FileNotFoundError(f"More than one file matches {pattern!r} in {folder}: {[m.name for m in matches]}")
    if not matches:
        if required:
            raise FileNotFoundError(f"No file matches {pattern!r} in {folder}")
        return None
    return matches[0]


def parse_time(values):
    """Epoch seconds or date strings -> timezone-naive UTC datetime64[ns]."""
    s = pd.Series(values)
    if pd.api.types.is_numeric_dtype(s):
        t = pd.to_datetime(s, unit="s", utc=True)
    else:
        t = pd.to_datetime(s, utc=True, format="mixed")
    return t.dt.tz_localize(None).astype("datetime64[ns]")


def read_columns(path, wanted):
    """Read only the columns in `wanted` that exist in the CSV (keeps memory low for big files)."""
    header = pd.read_csv(path, nrows=0).columns
    return pd.read_csv(path, usecols=[c for c in header if c in set(wanted)])


def apply_mapping(df, mapping, time_col, source_file, fill_values=None):
    """
    Rename and convert columns.

    mapping: {native_column: (OG1_NAME, converter)} where converter is a
             function applied to the column, or None to copy as-is.
    fill_values: {native_column: [values meaning "missing"]}, turned into NaN.
    Columns missing from the file are skipped, so one mapping can serve
    slightly different file versions.
    Data are stored as float32 (ample precision for glider sensors, half the memory).
    """
    out = pd.DataFrame({"TIME": parse_time(df[time_col])})
    attrs = {}
    fill_values = fill_values or {}
    for native, (name, convert) in mapping.items():
        if native not in df.columns:
            continue
        col = pd.to_numeric(df[native], errors="coerce")
        if native in fill_values:
            col = col.mask(col.isin(fill_values[native]))
        out[name] = (convert(col) if convert else col).astype("float32")
        attrs[name] = {"source_column": native, "source_file": Path(source_file).name}
    out = out.dropna(subset=["TIME"]).drop_duplicates("TIME").sort_values("TIME")
    return out.reset_index(drop=True), attrs


def merge_on_time(frames):
    """Outer-merge timeseries on TIME. Rows keep NaN where a stream has no sample."""
    frames = [f for f in frames if f is not None and len(f)]
    merged = frames[0]
    for f in frames[1:]:
        overlap = [c for c in f.columns if c != "TIME" and c in merged.columns]
        if overlap:
            raise ValueError(f"Variables provided by two input streams: {overlap}")
        merged = merged.merge(f, on="TIME", how="outer")
    return merged.sort_values("TIME").reset_index(drop=True)


def valid_positions(time, lat, lon):
    """Build a positions/gps frame, dropping fill values and impossible coordinates."""
    df = pd.DataFrame({"TIME": parse_time(time), "LATITUDE": pd.to_numeric(lat, errors="coerce"),
                       "LONGITUDE": pd.to_numeric(lon, errors="coerce")})
    ok = df.LATITUDE.between(-90, 90) & df.LONGITUDE.between(-180, 180)
    return df[ok].dropna().drop_duplicates("TIME").sort_values("TIME").reset_index(drop=True)


def as_gps(positions, max_speed_m_s=10.0):
    """Rename to the *_GPS names, dropping isolated bad fixes.

    A fix is dropped when reaching it from the previous fix AND leaving it for the
    next one would both need more than `max_speed_m_s` (a glider, or even the
    recovery boat, cannot do that; e.g. a corrupt fix 2000 km away).
    """
    p = positions.sort_values("TIME").reset_index(drop=True)
    if len(p) >= 3:
        lat, lon = np.radians(p.LATITUDE.to_numpy()), np.radians(p.LONGITUDE.to_numpy())
        dist = 2 * 6371e3 * np.arcsin(np.sqrt(np.sin(np.diff(lat) / 2) ** 2 +
                                              np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(np.diff(lon) / 2) ** 2))
        dt = np.maximum(np.diff(p.TIME.to_numpy()).astype("timedelta64[ms]").astype(float) / 1000, 1.0)
        fast = dist / dt > max_speed_m_s
        spike = np.r_[fast[0], fast[:-1] & fast[1:], fast[-1]]
        p = p[~spike]
    return p.rename(columns={"LATITUDE": "LATITUDE_GPS", "LONGITUDE": "LONGITUDE_GPS"}).reset_index(drop=True)
