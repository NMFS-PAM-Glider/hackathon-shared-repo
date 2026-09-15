"""
File: glider-og1/glider_og1/readers/seaglider.py

What it does: Reads Seaglider CSV exports produced by agate
    (https://sfregosi.github.io/agate/) and maps them to OG1 names and units.

How to run: used by convert.py when a deployment YAML has `reader: seaglider`.

Inputs (in the deployment folder, matched by the `files` patterns in the YAML):
    engineering  *flight_timeseries_engineering.csv  (pitch/roll/heading in degrees, vbdCC)
    modeled      *flight_timeseries_modeled.csv      (flight model speeds in cm/s)
    science      *science_timeseries.csv             (CTD; positions are dead-reckoned)
    gps          *GPS_timeseries.csv                 (one row per dive: start/end fix, depth-averaged current)
Outputs: a GliderData object (see readers/common.py)

Notes:
    - The Seaglider CTD has no pressure column in these exports, so PRES is absent.
    - Depth-averaged current (dac_e/dac_n) is per dive; it is written on every row of that dive.
"""

import pandas as pd

from .common import GliderData, apply_mapping, as_gps, find_file, merge_on_time, valid_positions

cm_s = lambda x: x / 100.0  # noqa: E731

ENGINEERING = {
    "dive": ("DIVE_NUMBER", None),
    "pitch": ("GLIDER_PITCH", None),
    "roll": ("GLIDER_ROLL", None),
    "heading": ("GLIDER_HEADING", None),
    "vbdCC": ("GLIDER_RELATIVE_VBD", None),
}

MODELED = {
    "vertSpeed": ("GLIDER_VERT_VELO_MODEL", cm_s),  # already positive up (negative on descent)
    "horzSpeed": ("GLIDER_HORZ_VELO_MODEL", cm_s),
    "speed": ("GLIDER_SPEED_MODEL", cm_s),
    "glideAngle": ("GLIDE_ANGLE_MODEL", None),
    "buoyancy": ("BUOYANCY_MODEL", None),
}

SCIENCE = {
    "depth": ("DEPTH", None),
    "temperature": ("TEMP", None),
    "salinity": ("PSAL", None),
    "density": ("DENSITY", None),
    "soundVelocity": ("SOUNDVEL", None),
}


def read(folder, files):
    eng_path = find_file(folder, files["engineering"])
    mod_path = find_file(folder, files.get("modeled", "*flight_timeseries_modeled.csv"), required=False)
    sci_path = find_file(folder, files["science"], required=False)
    gps_path = find_file(folder, files["gps"])

    eng, attrs = apply_mapping(pd.read_csv(eng_path), ENGINEERING, "time", eng_path)
    frames, sources = [eng], [eng_path]

    if mod_path:
        mod_raw = pd.read_csv(mod_path)
        mod, mod_attrs = apply_mapping(mod_raw, MODELED, "time", mod_path)
        frames.append(mod)
        attrs.update(mod_attrs)
        sources.append(mod_path)

    positions = pd.DataFrame(columns=["TIME", "LATITUDE", "LONGITUDE"])
    if sci_path:
        sci_raw = pd.read_csv(sci_path)
        sci, sci_attrs = apply_mapping(sci_raw, SCIENCE, "time", sci_path)
        frames.append(sci)
        attrs.update(sci_attrs)
        sources.append(sci_path)
        positions = valid_positions(sci_raw.time, sci_raw.latitude, sci_raw.longitude)

    g = pd.read_csv(gps_path)
    sources.append(gps_path)
    gps = pd.concat([valid_positions(g.startTime, g.startLatitude, g.startLongitude),
                     valid_positions(g.endTime, g.endLatitude, g.endLongitude)])
    gps = gps.drop_duplicates("TIME").sort_values("TIME").reset_index(drop=True)

    data = merge_on_time(frames)
    if {"dac_e", "dac_n"} <= set(g.columns) and "DIVE_NUMBER" in data:
        dac = g.set_index("dive")[["dac_e", "dac_n"]]
        data["WATERCURRENTS_U"] = data.DIVE_NUMBER.map(dac.dac_e)
        data["WATERCURRENTS_V"] = data.DIVE_NUMBER.map(dac.dac_n)
        for name, col in (("WATERCURRENTS_U", "dac_e"), ("WATERCURRENTS_V", "dac_n")):
            attrs[name] = {"source_column": col, "source_file": gps_path.name,
                           "comment": "one value per dive, repeated on every row of that dive"}

    return GliderData(data, positions, as_gps(gps), sources, attrs)
