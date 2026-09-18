"""
File: glider-og1/glider_og1/readers/slocum.py

What it does: Reads Teledyne Webb Slocum CSV exports produced by the SWFSC
    processing (pyglider/esdglider) and maps them to OG1 names and units.

How to run: used by convert.py when a deployment YAML has `reader: slocum`.

Inputs (in the deployment folder, matched by the `files` patterns in the YAML):
    engineering  *flight_timeseries_engineering.csv   (m_* / c_* columns, radians)
    science      *science_timeseries.csv              (CTD, S/m)
    gps          *GPS_timeseries.csv                  (optional; used if engineering has no fixes)
Outputs: a GliderData object (see readers/common.py)

Notes:
    - Use time_utc, not time: `time` is truncated to whole seconds and repeats in the science file.
    - m_gps_lat/lon hold fill values (e.g. 696970.15) when there is no fix; those are dropped.
"""

import pandas as pd

from .common import RAD2DEG, GliderData, apply_mapping, as_gps, find_file, merge_on_time, read_columns, valid_positions

deg = lambda x: x * RAD2DEG  # noqa: E731

ENGINEERING = {
    "m_depth": ("GLIDER_DEPTH", None),
    "m_pitch": ("GLIDER_PITCH", deg),
    "m_roll": ("GLIDER_ROLL", deg),
    "m_heading": ("GLIDER_HEADING", deg),
    "m_battery": ("BATTERY_VOLTAGE", None),
    "m_battpos": ("GLIDER_PITCH_MASS_POSITION", lambda x: x * 0.0254),  # inches -> m
    "m_coulomb_amphr": ("BATTERY_CHARGE_USED", None),
    "m_coulomb_amphr_total": ("BATTERY_CHARGE_USED_TOTAL", None),
    "m_coulomb_current": ("BATTERY_CURRENT", None),
    "m_de_oil_vol": ("OIL_VOL", None),
    "m_depth_rate": ("GLIDER_DEPTH_RATE", None),
    "m_fin": ("FIN_ANGLE", deg),
    "m_speed": ("GLIDER_SPEED", None),
    "m_speed_avg": ("GLIDER_SPEED_AVG", None),
    "c_de_oil_vol": ("OIL_VOL_COMMANDED", None),
    "c_pitch": ("GLIDER_PITCH_COMMANDED", deg),
    "c_fin": ("FIN_ANGLE_COMMANDED", deg),
}

SCIENCE = {
    "depth": ("DEPTH", None),
    "pressure": ("PRES", None),
    "temperature": ("TEMP", None),
    "conductivity": ("CNDC", lambda x: x * 10.0),  # S/m -> mS/cm
    "salinity": ("PSAL", None),
    "density": ("DENSITY", None),
    "potential_temperature": ("THETA", None),
    "potential_density": ("POTDENS", None),
}


def read(folder, files):
    eng_path = find_file(folder, files["engineering"])
    sci_path = find_file(folder, files["science"], required=False)
    gps_path = find_file(folder, files.get("gps", "*GPS_timeseries.csv"), required=False)

    eng_raw = read_columns(eng_path, ["time_utc", "m_gps_lat", "m_gps_lon", *ENGINEERING])
    eng, attrs = apply_mapping(eng_raw, ENGINEERING, "time_utc", eng_path)
    frames, sources = [eng], [eng_path]

    positions = pd.DataFrame(columns=["TIME", "LATITUDE", "LONGITUDE"])
    if sci_path:
        sci_raw = read_columns(sci_path, ["time_utc", "latitude", "longitude", *SCIENCE])
        sci, sci_attrs = apply_mapping(sci_raw, SCIENCE, "time_utc", sci_path)
        frames.append(sci)
        attrs.update(sci_attrs)
        sources.append(sci_path)
        positions = valid_positions(sci_raw.time_utc, sci_raw.latitude, sci_raw.longitude)

    gps = valid_positions(eng_raw.time_utc, eng_raw.m_gps_lat, eng_raw.m_gps_lon)
    if gps.empty and gps_path:
        g = pd.read_csv(gps_path)
        gps = valid_positions(g.startTime, g.latitude, g.longitude)
        sources.append(gps_path)

    return GliderData(merge_on_time(frames), positions, as_gps(gps), sources, attrs)
