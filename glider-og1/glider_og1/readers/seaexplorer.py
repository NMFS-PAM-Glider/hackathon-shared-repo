"""
File: glider-og1/glider_og1/readers/seaexplorer.py

What it does: Reads ALSEAMAR SeaExplorer CSV exports (as prepared for SEA117 in
    the Glider Rodeo) and maps them to OG1 names and units.

How to run: used by convert.py when a deployment YAML has `reader: seaexplorer`.

Inputs (in the deployment folder, matched by the `files` patterns in the YAML):
    engineering    *flight_timeseries_engineering.csv  (NavState, attitude, ballast/motors, voltage)
    science        *science_timeseries.csv             (RBR Legato CTD, conductivity in mS/cm; storage use)
    gps            *GPS_timeseries.csv                 (surface fixes)
    dead_reckoned  *dead-reckoned_timeseries.csv       (underwater position estimates)
Outputs: a GliderData object (see readers/common.py)

Notes:
    - The engineering file is not in time order; rows are sorted on read.
    - Left out on purpose: PressureNav/PressureRel (values are in bar although
      documented as dbar; GLIDER_DEPTH covers the same information), Humidity
      (always -999), Altitude (only -1/0: altimeter not used), and the science
      file's NAV_* columns (copies of the engineering data).
    - NavState text is stored as NAV_STATE codes; the meanings are in its attributes.
"""

import pandas as pd

from .common import GliderData, apply_mapping, as_gps, find_file, merge_on_time, read_columns, valid_positions

ENGINEERING = {
    "YO_NUMBER": ("DIVE_NUMBER", None),
    "Heading": ("GLIDER_HEADING", None),
    "Pitch": ("GLIDER_PITCH", None),
    "Roll": ("GLIDER_ROLL", None),
    "Depth": ("GLIDER_DEPTH", None),
    "Temperature": ("INTERNAL_TEMPERATURE", None),
    "Pa": ("INTERNAL_PRESSURE", None),
    "DesiredH": ("GLIDER_HEADING_COMMANDED", None),
    "BallastCmd": ("BALLAST_COMMANDED", None),
    "BallastPos": ("BALLAST_POSITION", None),
    "LinCmd": ("PITCH_MOTOR_COMMANDED", None),
    "LinPos": ("PITCH_MOTOR_POSITION", None),
    "AngCmd": ("ROLL_MOTOR_COMMANDED", None),
    "AngPos": ("ROLL_MOTOR_POSITION", None),
    "Voltage": ("BATTERY_VOLTAGE", None),
}

SCIENCE = {
    "LEGATO_PRESSURE": ("PRES", None),
    "LEGATO_TEMPERATURE": ("TEMP", None),
    "LEGATO_CONDUCTIVITY": ("CNDC", None),  # already mS/cm
    "LEGATO_SALINITY": ("PSAL", None),
    "LEGATO_CONDTEMP": ("TEMP_CNDC", None),
    "LEGATO_SOUND_VELOCITY": ("SOUNDVEL", None),
    "LEGATO_POTENTIAL_DENSITY": ("POTDENS", None),
    "SD_CARD_USAGE": ("STORAGE_USED", None),
    "SSD_USAGE": ("STORAGE_USED_SSD", None),
}

NAV_STATES = ["ascent", "descent", "inflecting up", "inflecting down", "surfacing", "gps",
              "transmitting", "drifting", "ballasting"]


def read(folder, files):
    eng_path = find_file(folder, files["engineering"])
    sci_path = find_file(folder, files["science"], required=False)
    gps_path = find_file(folder, files["gps"])
    dr_path = find_file(folder, files.get("dead_reckoned", "*dead-reckoned_timeseries.csv"), required=False)

    eng_raw = read_columns(eng_path, ["Time", "NavState", *ENGINEERING])
    eng, attrs = apply_mapping(eng_raw, ENGINEERING, "Time", eng_path, fill_values={"DesiredH": [-9999]})

    codes = {state: i + 1 for i, state in enumerate(NAV_STATES)}
    unknown = sorted(set(eng_raw.NavState.dropna()) - set(codes))
    if unknown:
        raise ValueError(f"New NavState values, add them to NAV_STATES in seaexplorer.py: {unknown}")
    nav = pd.DataFrame({"TIME": pd.to_datetime(eng_raw.Time, unit="s"),
                        "NAV_STATE": eng_raw.NavState.map(codes).astype("float32")})
    eng = eng.merge(nav.drop_duplicates("TIME"), on="TIME", how="left")
    attrs["NAV_STATE"] = {"source_column": "NavState", "source_file": eng_path.name,
                          "flag_values": list(codes.values()),
                          "flag_meanings": " ".join(s.replace(" ", "_") for s in codes)}
    attrs["GLIDER_HEADING"]["comment"] = ("heading reference (magnetic or true) not stated in the source "
                                          "definitions; the file's Declination column is 9 degrees")
    frames, sources = [eng], [eng_path]

    if sci_path:
        sci_raw = read_columns(sci_path, ["Time", *SCIENCE])
        sci, sci_attrs = apply_mapping(sci_raw, SCIENCE, "Time", sci_path, fill_values={"SSD_USAGE": [-1]})
        frames.append(sci)
        attrs.update(sci_attrs)
        sources.append(sci_path)

    g = pd.read_csv(gps_path)
    gps = valid_positions(g.time_utc, g.latitude, g.longitude)
    sources.append(gps_path)

    positions = pd.DataFrame(columns=["TIME", "LATITUDE", "LONGITUDE"])
    if dr_path:
        d = pd.read_csv(dr_path)
        positions = valid_positions(d.time_utc, d.latitude, d.longitude)
        sources.append(dr_path)

    return GliderData(merge_on_time(frames), positions, as_gps(gps), sources, attrs)
