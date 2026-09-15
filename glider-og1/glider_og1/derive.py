"""
File: glider-og1/glider_og1/derive.py

What it does: Fills in the OG1 variables that the source files do not provide
    directly, using the same method for every glider so the results can be
    compared across platforms:
      - LATITUDE / LONGITUDE on every row (time interpolation between known positions)
      - DEPTH on every row (source depth, gaps up to `max_depth_gap_s` interpolated)
      - DEPTH_Z and GLIDER_VERT_VELO_DZDT
      - PHASE, PROFILE_DIRECTION, PROFILE_NUMBER, SEGMENT_NUMBER from the depth record

How to run: called by build.py; the thresholds can be overridden per deployment
    under `derive:` in the deployment YAML.

Inputs: a merged data frame from a reader (see readers/common.py)
Outputs: the same frame with the derived columns added, plus attribute comments
"""

import numpy as np
import pandas as pd

DEFAULTS = {
    "surface_depth_m": 2.0,      # shallower than this counts as surfacing
    "vertical_speed_threshold": 0.03,  # m/s; slower than this below the surface = parking/inflection
    "smooth_window_s": 60,       # window for depth smoothing and vertical speed averaging
    "min_profile_duration_s": 60,
    "min_profile_extent_m": 5.0,
    "parking_min_duration_s": 300,  # still for at least this long = parking (drift), else inflection
    "profile_merge_gap_s": 300,  # same-direction pieces closer than this (and depth-continuous) form one profile
    "max_depth_gap_s": 120,      # longest gap in depth that is interpolated
}

UNKNOWN, ASCENT, DESCENT, SURFACING, PARKING, INFLECTION, PROPELLED, TRANSITION = range(8)


def _seconds(time):
    return (pd.to_datetime(time) - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()


def interpolate_positions(data, positions, gps):
    """LATITUDE/LONGITUDE at every TIME, interpolated from GPS fixes plus source positions."""
    known = pd.concat([
        gps.rename(columns={"LATITUDE_GPS": "LATITUDE", "LONGITUDE_GPS": "LONGITUDE"}),
        positions,
    ]).dropna().drop_duplicates("TIME").sort_values("TIME")
    t = _seconds(data.TIME)
    tk = _seconds(known.TIME)
    for col in ("LATITUDE", "LONGITUDE"):
        data[col] = np.interp(t, tk, known[col].to_numpy(), left=np.nan, right=np.nan)
    return {
        "comment": "linearly interpolated in time between GPS fixes and the source's dead-reckoned/"
                   "interpolated positions; not extrapolated beyond the first and last known position",
    }


def fill_depth(data, max_gap_s):
    """DEPTH on every row: measured depth where available, short gaps interpolated."""
    depth = data["DEPTH"] if "DEPTH" in data else pd.Series(np.nan, index=data.index)
    sources = ["DEPTH"] if "DEPTH" in data else []
    if "GLIDER_DEPTH" in data:
        depth = depth.combine_first(data["GLIDER_DEPTH"])
        sources.append("GLIDER_DEPTH")
    t = _seconds(data.TIME)
    ok = depth.notna().to_numpy()
    filled = np.interp(t, t[ok], depth.to_numpy()[ok], left=np.nan, right=np.nan)
    # only accept interpolation across gaps shorter than max_gap_s
    tv = pd.Series(np.where(ok, t, np.nan))
    gap = tv.bfill().to_numpy() - tv.ffill().to_numpy()
    filled[~ok & ~(gap <= max_gap_s)] = np.nan
    data["DEPTH"] = filled
    data["DEPTH_Z"] = -filled
    return {"comment": f"from {' then '.join(sources)}; gaps up to {max_gap_s} s linearly interpolated"}


def _runs(values):
    """Start index, end index (exclusive) and value of each run of equal values."""
    change = np.flatnonzero(np.diff(values)) + 1
    starts = np.r_[0, change]
    ends = np.r_[change, len(values)]
    return starts, ends, values[starts]


def derive_phase(data, cfg):
    """PHASE, PROFILE_DIRECTION, PROFILE_NUMBER, SEGMENT_NUMBER, GLIDER_VERT_VELO_DZDT."""
    n = len(data)
    phase = np.full(n, UNKNOWN, dtype=np.int8)
    w_up = np.full(n, np.nan)
    z_smooth = np.full(n, np.nan)

    ok = data.DEPTH.notna().to_numpy()
    idx = np.flatnonzero(ok)
    if len(idx) > 2:
        window = f"{cfg['smooth_window_s']}s"
        z = pd.Series(data.DEPTH.to_numpy()[ok], index=pd.DatetimeIndex(data.TIME.to_numpy()[ok]))
        zs = z.rolling(window, center=True, min_periods=1).median()
        t = _seconds(pd.Series(zs.index))
        dt = np.gradient(t)
        dt[dt == 0] = np.nan
        w_down = pd.Series(np.gradient(zs.to_numpy()) / dt, index=zs.index)
        w_down = w_down.rolling(window, center=True, min_periods=1).mean().to_numpy()
        w_up[ok] = -w_down
        z_smooth[ok] = zs.to_numpy()

        thr = cfg["vertical_speed_threshold"]
        state = np.where(zs.to_numpy() < cfg["surface_depth_m"], SURFACING,
                         np.where(w_down > thr, DESCENT, np.where(w_down < -thr, ASCENT, INFLECTION)))
        state = np.where(np.isnan(w_down) & (state != SURFACING), UNKNOWN, state).astype(np.int8)

        zv = zs.to_numpy()
        for s, e, v in zip(*_runs(state)):
            duration = t[e - 1] - t[s]
            if v in (ASCENT, DESCENT):
                if duration < cfg["min_profile_duration_s"] or abs(zv[e - 1] - zv[s]) < cfg["min_profile_extent_m"]:
                    state[s:e] = TRANSITION
            elif v == INFLECTION and duration >= cfg["parking_min_duration_s"]:
                state[s:e] = PARKING
        phase[idx] = state

    direction = np.where(phase == DESCENT, 1, np.where(phase == ASCENT, -1, 0)).astype(np.int8)

    # Rows between profiles (surfacing, inflection, parking) keep the number of the
    # preceding profile, as in the community OG1 example files glidertest is built on.
    # Same-direction pieces separated by a gap are one profile only if the gap is short AND
    # the smoothed depth carries on (a descent cannot restart much shallower, an ascent much
    # deeper). This keeps dives with short data gaps whole but separates back-to-back dives
    # whose climb was not sampled (e.g. CTD recording on descent only).
    profile = np.zeros(n, dtype=np.int32)
    t_all = _seconds(data.TIME)
    jump = cfg["min_profile_extent_m"]
    count, last_dir, last_t, last_z = 0, 0, -np.inf, np.nan
    for i in np.flatnonzero(direction != 0):
        gap = t_all[i] - last_t
        restarted = gap > cfg["smooth_window_s"] and (
            (direction[i] == 1 and z_smooth[i] < last_z - jump) or
            (direction[i] == -1 and z_smooth[i] > last_z + jump))
        if direction[i] != last_dir or gap > cfg["profile_merge_gap_s"] or restarted:
            count += 1
            profile[i:] = count
        last_dir, last_t, last_z = direction[i], t_all[i], z_smooth[i]

    at_surface = phase == SURFACING
    entering = at_surface & ~np.r_[False, at_surface[:-1]]
    segment = (np.cumsum(entering) + (0 if at_surface[:1].all() else 1)).astype(np.int32)

    data["PHASE"] = phase
    data["PROFILE_DIRECTION"] = direction
    data["PROFILE_NUMBER"] = profile
    data["SEGMENT_NUMBER"] = segment
    data["GLIDER_VERT_VELO_DZDT"] = w_up

    method = ("derived from DEPTH: depth smoothed with a {smooth_window_s} s running median, vertical speed "
              "averaged over {smooth_window_s} s; surfacing above {surface_depth_m} m; ascent/descent faster than "
              "{vertical_speed_threshold} m/s lasting at least {min_profile_duration_s} s and "
              "{min_profile_extent_m} m (else transition); slower periods are parking if they last "
              "{parking_min_duration_s} s or more, else inflection").format(**cfg)
    return {
        "PHASE": {"phase_calculation_method": method},
        "GLIDER_VERT_VELO_DZDT": {"comment": f"from DEPTH, smoothed over {cfg['smooth_window_s']} s"},
    }


def derive_all(data, positions, gps, overrides=None):
    cfg = {**DEFAULTS, **(overrides or {})}
    attrs = {"LATITUDE": interpolate_positions(data, positions, gps)}
    attrs["LONGITUDE"] = attrs["LATITUDE"]
    attrs["DEPTH"] = fill_depth(data, cfg["max_depth_gap_s"])
    attrs.update(derive_phase(data, cfg))
    return attrs
