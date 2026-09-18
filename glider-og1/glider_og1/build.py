"""
File: glider-og1/glider_og1/build.py

What it does: Turns a reader's GliderData plus a deployment YAML into an
    OG1.0 xarray Dataset (single N_MEASUREMENTS dimension, CF/OG1 attributes,
    QC companions, platform/sensor/deployment metadata variables), and writes
    it to NetCDF with the OG1 file name <platform_serial>_<start>_<data_mode>.nc.

How to run: called by convert.py.

Inputs: GliderData (readers/common.py), deployment config dict (deployments/*.yaml)
Outputs: xarray.Dataset; NetCDF file when write_og1() is called
"""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from . import __version__
from .derive import derive_all
from .variables import QC_ATTRS, QC_VARIABLES, attrs_for, is_registered, sensor_type_for

DIM = "N_MEASUREMENTS"
OG1_TIME_UNITS = "seconds since 1970-01-01T00:00:00Z"
COORDS = ["TIME", "LATITUDE", "LONGITUDE", "DEPTH"]
MIN_VALID_DEPTH = -2.0  # m; shallower readings are flagged bad in DEPTH_QC
# PROFILE_DIRECTION has no fill value on purpose: the spec's _FillValue=0 would turn
# "not profiling" (0) into NaN on read, so `PROFILE_DIRECTION != 0` would match those rows.
INT_VARS = {"PHASE": ("int8", 0), "PROFILE_DIRECTION": ("int8", None),
            "PROFILE_NUMBER": ("int32", None), "SEGMENT_NUMBER": ("int32", -9999)}


def _iso(ts):
    return pd.Timestamp(ts).strftime("%Y%m%dT%H%M%S")


def _sensor_var_name(sensor):
    serial = "".join(ch if ch.isalnum() else "_" for ch in str(sensor.get("serial", "unknown")))
    return f"SENSOR_{sensor['type'].upper()}_{serial}"


def build_dataset(glider, config):
    data = glider.data.copy()

    # GPS fixes become rows of their own so TIME_GPS/LATITUDE_GPS share N_MEASUREMENTS.
    gps = glider.gps.copy()
    gps["TIME_GPS"] = gps.TIME
    data = data.merge(gps, on="TIME", how="outer").sort_values("TIME").reset_index(drop=True)

    derived_attrs = derive_all(data, glider.positions, glider.gps, config.get("derive"))

    unknown = [c for c in data.columns if c not in ("TIME", "TIME_GPS") and not is_registered(c)]
    if unknown:
        raise KeyError(f"Columns without an entry in variables.py: {unknown}")

    ds = xr.Dataset(coords={"TIME": (DIM, data.TIME.to_numpy())})
    sensors = {s["type"].upper(): _sensor_var_name(s) for s in config.get("sensors", [])}

    for name in data.columns:
        if name == "TIME":
            continue
        values = data[name].to_numpy()
        if name == "TIME_GPS":
            ds[name] = (DIM, pd.to_datetime(values).to_numpy())
            ds[name].attrs = {"long_name": "time of each GPS fix", "standard_name": "time"}
            continue
        attrs = attrs_for(name)
        attrs.update(glider.var_attrs.get(name, {}))
        attrs.update(derived_attrs.get(name, {}))
        sensor_type = sensor_type_for(name)
        if sensor_type and sensor_type in sensors:
            attrs["sensor"] = sensors[sensor_type]
        if name in INT_VARS:
            dtype, fill = INT_VARS[name]
            ds[name] = (DIM, values.astype(dtype))
            if fill is not None:
                ds[name].encoding["_FillValue"] = np.array(fill, dtype=dtype)
        else:
            dtype = "float32" if values.dtype == np.float32 else "float64"
            ds[name] = (DIM, values.astype(dtype, copy=False))
        ds[name].attrs = attrs

    ds["TIME"].attrs = {"long_name": "time of measurement", "standard_name": "time", "axis": "T"}
    ds = ds.set_coords([c for c in COORDS if c in ds])

    for name in QC_VARIABLES:
        if name in ds:
            ds[f"{name}_QC"] = (DIM, np.zeros(ds.sizes[DIM], dtype="int8"))
            ds[f"{name}_QC"].attrs = dict(QC_ATTRS)
            ds[name].attrs["ancillary_variables"] = f"{name}_QC"

    # The only QC applied: physically impossible depths (e.g. a pressure offset while
    # the glider is on deck) are kept but flagged bad.
    bad_depth = ds.DEPTH.values < MIN_VALID_DEPTH
    ds["DEPTH_QC"].values[bad_depth] = 4
    ds["DEPTH_QC"].attrs["comment"] = f"4 (bad) where DEPTH < {MIN_VALID_DEPTH} m; no other QC applied"

    _add_metadata_variables(ds, data, config)
    ds.attrs = _global_attributes(ds, glider, config)
    return ds


def _add_metadata_variables(ds, data, config):
    p = config["platform"]
    start = _iso(data.TIME.iloc[0])
    scalar = {
        "TRAJECTORY": (f"{p['serial_number']}_{start}", {"long_name": "trajectory name", "cf_role": "trajectory_id"}),
        "WMO_IDENTIFIER": (str(p.get("wmo_id", "")), {"long_name": "wmo id"}),
        "PLATFORM_MODEL": (p["model"], {"long_name": "model of the glider",
                                        "platform_model_vocabulary": p.get("model_vocabulary", "")}),
        "PLATFORM_SERIAL_NUMBER": (p["serial_number"], {"long_name": "glider serial number"}),
        "PLATFORM_NAME": (config["glider_name"], {"long_name": "Local or nickname of the glider"}),
        "PLATFORM_MAKER": (p.get("maker", ""), {"long_name": "glider manufacturer",
                                                "platform_maker_vocabulary": p.get("maker_vocabulary", "")}),
        "BATTERY_TYPE": (str(p.get("battery_type", "")), {"long_name": "battery type"}),
        "BATTERY_PACK": (str(p.get("battery_capacity", "")), {"long_name": "battery pack capacity"}),
    }
    if p.get("depth_rating"):
        scalar["PLATFORM_DEPTH_RATING"] = (np.int32(p["depth_rating"]),
                                           {"long_name": "glider depth rating", "units": "m"})
    for name, (value, attrs) in scalar.items():
        ds[name] = ((), value, attrs)

    first = ds.LATITUDE_GPS.notnull() if "LATITUDE_GPS" in ds else ds.LATITUDE.notnull()
    i = int(np.argmax(first.to_numpy())) if bool(first.any()) else 0
    lat = ds.LATITUDE_GPS if "LATITUDE_GPS" in ds else ds.LATITUDE
    lon = ds.LONGITUDE_GPS if "LONGITUDE_GPS" in ds else ds.LONGITUDE
    ds["DEPLOYMENT_TIME"] = ((), ds.TIME.values[i], {"long_name": "date of deployment", "standard_name": "time"})
    ds["DEPLOYMENT_LATITUDE"] = ((), float(lat.values[i]), {"long_name": "latitude of deployment",
                                                            "standard_name": "latitude", "units": "degrees_north"})
    ds["DEPLOYMENT_LONGITUDE"] = ((), float(lon.values[i]), {"long_name": "longitude of deployment",
                                                             "standard_name": "longitude", "units": "degrees_east"})

    for sensor in config.get("sensors", []):
        attrs = {
            "long_name": sensor.get("model", sensor["type"]),
            "sensor_type_vocabulary": sensor.get("type_vocabulary", ""),
            "sensor_model": sensor.get("model", ""),
            "sensor_model_vocabulary": sensor.get("model_vocabulary", ""),
            "sensor_maker": sensor.get("maker", ""),
            "sensor_maker_vocabulary": sensor.get("maker_vocabulary", ""),
            "sensor_serial_number": str(sensor.get("serial", "unknown")),
        }
        attrs.update({k: str(v) for k, v in sensor.get("attributes", {}).items()})
        if sensor.get("calibration_date"):
            attrs["sensor_calibration_date"] = str(sensor["calibration_date"])
        ds[_sensor_var_name(sensor)] = ((), "", attrs)


def _global_attributes(ds, glider, config):
    p = config["platform"]
    time = pd.to_datetime(ds.TIME.values)
    start = _iso(time[0])
    mode = config.get("data_mode", "delayed")
    now = datetime.now(timezone.utc)
    attrs = {
        "title": "OceanGliders trajectory file",
        "platform": "sub-surface gliders",
        "platform_vocabulary": "https://vocab.nerc.ac.uk/collection/L06/current/27/",
        "id": f"{p['serial_number']}_{start}_{mode}",
        "featureType": "trajectory",
        "Conventions": "CF-1.10, ACDD-1.3, OG-1.0",
        "start_date": start,
        "date_created": now.strftime("%Y%m%dT%H%M%S"),
        "rtqc_method": f"No QC applied, except DEPTH_QC = 4 where DEPTH < {MIN_VALID_DEPTH} m",
        "rtqc_method_doi": "n/a",
        "internal_mission_identifier": config["deployment_id"],
        "time_coverage_start": start,
        "time_coverage_end": _iso(time[-1]),
        "geospatial_lat_min": float(ds.LATITUDE.min()),
        "geospatial_lat_max": float(ds.LATITUDE.max()),
        "geospatial_lon_min": float(ds.LONGITUDE.min()),
        "geospatial_lon_max": float(ds.LONGITUDE.max()),
        "geospatial_vertical_min": float(ds.DEPTH.min()),
        "geospatial_vertical_max": float(ds.DEPTH.max()),
    }
    attrs.update({k: v for k, v in config.get("attributes", {}).items() if v not in (None, "")})
    attrs["history"] = (f"{now:%Y-%m-%dT%H:%M:%SZ} converted to OG1 by glider-og1 {__version__} from: "
                        + ", ".join(Path(s).name for s in glider.sources))
    return attrs


def og1_filename(ds):
    return f"{ds.attrs['id']}.nc"


def write_og1(ds, out_dir):
    out = Path(out_dir) / og1_filename(ds)
    out.parent.mkdir(parents=True, exist_ok=True)
    encoding = {}
    for name, var in ds.variables.items():
        enc = dict(var.encoding)
        if np.issubdtype(var.dtype, np.datetime64):
            enc.update(units=OG1_TIME_UNITS, dtype="float64", calendar="gregorian")
        if var.ndim and var.dtype.kind in "fiuM":
            enc.update(zlib=True, complevel=4)
        encoding[name] = enc
    ds.to_netcdf(out, encoding=encoding, format="NETCDF4")
    return out
