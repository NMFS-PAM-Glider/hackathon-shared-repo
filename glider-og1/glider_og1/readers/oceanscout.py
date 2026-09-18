"""
File: glider-og1/glider_og1/readers/oceanscout.py

What it does: Reads Hefring Oceanscout CSV exports (as prepared for Belladonna
    in the Glider Rodeo) and maps them to OG1 names and units.

How to run: used by convert.py when a deployment YAML has `reader: oceanscout`.

Inputs (in the deployment folder, matched by the `files` patterns in the YAML):
    science  *_science.csv  (JFE CT sensor: depth, pressure, S/m conductivity, positions)
    gps      *_GPS.csv      (surface fixes)
Outputs: a GliderData object (see readers/common.py)

Notes:
    - No engineering export exists for this glider, so the OG1 file has CTD,
      positions and the derived dive phases only.
    - dive_index is -1 before the first dive; stored as missing.
    - The CTD timestamps arrive in bursts (samples < 1 ms apart, then a gap), so
      rates computed between neighbouring samples are not meaningful; use the
      smoothed GLIDER_VERT_VELO_DZDT instead.
    - The source field definitions have the latitude/longitude descriptions
      swapped; the column values themselves are correct.
"""

import pandas as pd

from .common import GliderData, apply_mapping, as_gps, find_file, merge_on_time, read_columns, valid_positions

SCIENCE = {
    "dive_index": ("DIVE_NUMBER", None),
    "depth_m": ("DEPTH", None),
    "pressure_dbar": ("PRES", None),
    "temperature_c": ("TEMP", None),
    "conductivity_S_m": ("CNDC", lambda x: x * 10.0),  # S/m -> mS/cm
    "salinity_psu": ("PSAL", None),
    "density_kg_m3": ("DENSITY", None),
    "sound_velocity_m_s": ("SOUNDVEL", None),
}


def read(folder, files):
    sci_path = find_file(folder, files["science"])
    gps_path = find_file(folder, files["gps"])

    sci_raw = read_columns(sci_path, ["time", "latitude", "longitude", *SCIENCE])
    sci, attrs = apply_mapping(sci_raw, SCIENCE, "time", sci_path, fill_values={"dive_index": [-1]})
    attrs["TEMP"]["comment"] = "CTD timestamps arrive in bursts; see the reader notes"

    positions = valid_positions(sci_raw.time, sci_raw.latitude, sci_raw.longitude)
    g = pd.read_csv(gps_path)
    gps = valid_positions(g.time, g.latitude, g.longitude)

    return GliderData(merge_on_time([sci]), positions, as_gps(gps), [sci_path, gps_path], attrs)
