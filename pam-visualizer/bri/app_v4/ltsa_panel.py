"""LTSA context panel for the Glider Audio Viewer.

Shows the deployment-scale Long Term Spectral Average underneath the three
signal panels, with the currently loaded .wav window marked in red, so a
60-second clip can be read against the days of recording around it.

Only drawn in the Spectrogram view: a waveform or a spectrum has no time axis
the LTSA can sit under in a way that means anything.

``render_ltsa_panel`` writes its own sidebar widgets, the same way
``data.load_data`` does, so ``app.py`` only has to call it.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ltsa import LTSAFile, LTSAError, parse_audio_time

# Averaging choices offered in the sidebar, coarsest-safe first.
AVERAGING_CHOICES = [
    ("Auto", "auto"),
    ("1 min", "1min"),
    ("5 min", "5min"),
    ("15 min", "15min"),
    ("1 hour", "1h"),
]

# Keep the heatmap to something a browser can draw, matching plots.py.
MAX_TIME_BINS = 700

# A marked window narrower than this fraction of the axis is drawn as a line,
# because a filled band that thin renders as nothing at all.
MIN_BAND_FRACTION = 1 / 250

# ---- colour bar defaults -------------------------------------------------
# Edit these to change what the Min/Max boxes start at and how far they can be
# pushed. Measured on sg607: below 60 kHz the levels sit in a ~35 dB band, so
# 90-125 puts the full colour range where the variation actually is. Above
# 60 kHz the anti-alias rolloff drags the floor down by another 60 dB, which is
# why the frequency ceiling matters as much as the colour limits.
DEFAULT_CLIM = (90.0, 125.0)    # (min_db, max_db) the boxes open at
CLIM_BOUNDS = (0.0, 200.0)      # how far the boxes can be pushed
CLIM_STEP = 1.0                 # dB per click of the +/- buttons

# Start with fixed limits rather than auto, so two recordings are comparable
# without anyone having to remember to pin them.
FIXED_CLIM_BY_DEFAULT = True

# Frequency ceiling the panel opens at. None follows the recording's Nyquist.
DEFAULT_FMAX_HZ = 60000.0


# Printed above every LTSA, because the plot is not self-explanatory to anyone
# meeting it for the first time.
LTSA_DEFINITION = (
    "A **Long Term Spectral Average (LTSA)** is a time-compressed spectrogram "
    "using the Welch algorithm, used to visualize acoustic signals in "
    "long-term recordings. Each time bin contains overlapping Hann-window "
    "spectra; bins of average spectra are aligned over time, resulting in "
    "long-term spectrograms where average processing preserves short-duration "
    "spectral features that may be lost in a shorter Fourier transform "
    "window. *(Developed by the Scripps Institution of Oceanography.)*"
)


# --------------------------------------------------------------------------
# discovery and caching
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def find_ltsa_files(ltsa_dir: str) -> pd.DataFrame:
    """Every .ltsa under *ltsa_dir*, with the glider name from the filename."""
    root = Path(ltsa_dir)
    if not root.is_dir():
        return pd.DataFrame(columns=["path", "glider", "stem"])

    rows = []
    for p in sorted(root.rglob("*.ltsa")):
        rows.append(
            {"path": str(p), "glider": p.stem.split("_")[0], "stem": p.stem}
        )
    return pd.DataFrame(rows)


@st.cache_resource(show_spinner=False)
def open_ltsa(path: str, mtime: float) -> LTSAFile:
    """One LTSAFile per file on disk; holds the memmap open across reruns."""
    return LTSAFile(path)


@st.cache_data(show_spinner="Reading LTSA…")
def read_ltsa(path: str, mtime: float, start, end, period, fmin, fmax):
    ltsa = open_ltsa(path, mtime)
    return ltsa.read(
        start=start, end=end, averaging_period=period, fmin=fmin, fmax=fmax
    )


# --------------------------------------------------------------------------
# matching a recording to an LTSA
# --------------------------------------------------------------------------
def glider_of(name) -> str:
    """The glider a file belongs to: the first underscore-delimited field."""
    return Path(str(name)).stem.split("_")[0]


def choose_ltsa(candidates: pd.DataFrame, source_name: str):
    """Pick the LTSA a recording belongs to, by glider name only.

    Deliberately no fallback to time containment. Two gliders flying the same
    deployment overlap in time, so a time match says nothing about whether the
    LTSA and the recording came from the same platform — and a marker drawn on
    another glider's LTSA is worse than no marker, because it looks right.
    When the name does not match, nothing is chosen and the panel says so.

    Returns ``(path or None, reason)``.
    """
    if candidates.empty:
        return None, "no .ltsa files found"

    glider = glider_of(source_name).lower()
    by_name = candidates[candidates["glider"].str.lower() == glider]

    if by_name.empty:
        return None, glider

    row = by_name.iloc[0]
    return row["path"], f"matched on glider name '{row['glider']}'"


def marked_window(df: pd.DataFrame):
    """The absolute UTC span of the slice currently loaded in the viewer.

    ``data.load_data`` records which part of the file was read, so the marker
    can show the actual loaded window rather than just the file's start.
    """
    stamp = parse_audio_time(df.attrs.get("source", ""))
    if stamp is None:
        return None, None

    start_s = float(df.attrs.get("start_s", 0.0))
    length_s = len(df) / float(df.attrs.get("sample_rate", 1) or 1)

    begin = stamp + pd.Timedelta(seconds=start_s)
    return begin, begin + pd.Timedelta(seconds=length_s)


# --------------------------------------------------------------------------
# figure
# --------------------------------------------------------------------------
def _auto_period(span: pd.Timedelta, native_s: float) -> str | None:
    """Coarsest averaging that still fills the axis, so the draw stays quick."""
    needed = span.total_seconds() / MAX_TIME_BINS
    for alias, seconds in [
        (None, native_s), ("10s", 10), ("30s", 30), ("1min", 60),
        ("5min", 300), ("15min", 900), ("1h", 3600),
    ]:
        if seconds >= needed:
            return alias
    return "3h"


def auto_clim(psd) -> tuple[float, float]:
    """Percentile colour limits. Straight min/max is dominated by a handful of
    extreme bins and washes everything else out."""
    return (
        float(np.nanpercentile(psd, 2)),
        float(np.nanpercentile(psd, 98)),
    )


def build_figure(
    ltsa: LTSAFile,
    times,
    freq,
    psd,
    mark_start=None,
    mark_end=None,
    mark_label="",
    colorscale="Viridis",
    clim=None,
) -> go.Figure:
    """Heatmap of the LTSA with the loaded window marked in red.

    ``clim`` is an explicit ``(min_db, max_db)`` for the colour bar; ``None``
    falls back to the 2nd-98th percentile of the data on screen.
    """
    if clim is not None:
        zmin, zmax = float(clim[0]), float(clim[1])
    else:
        zmin, zmax = auto_clim(psd)

    fig = go.Figure(
        go.Heatmap(
            x=times, y=freq, z=np.round(psd.T, 1).astype(np.float32),
            zmin=zmin, zmax=zmax, colorscale=colorscale, zsmooth=False,
            colorbar=dict(title="dB re 1 µPa", thickness=12),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>f=%{y:.0f}Hz"
                          "<br>%{z:.1f} dB<extra></extra>",
        )
    )

    if mark_start is not None:
        axis_span = (times[-1] - times[0]).total_seconds()
        window_span = (
            (mark_end - mark_start).total_seconds() if mark_end is not None else 0.0
        )

        if axis_span > 0 and window_span / axis_span >= MIN_BAND_FRACTION:
            fig.add_shape(
                type="rect", xref="x", yref="paper",
                x0=mark_start.isoformat(), x1=mark_end.isoformat(), y0=0, y1=1,
                fillcolor="red", opacity=0.30, line_width=0, layer="above",
            )
        else:
            fig.add_shape(
                type="line", xref="x", yref="paper",
                x0=mark_start.isoformat(), x1=mark_start.isoformat(), y0=0, y1=1,
                line=dict(color="red", width=2), layer="above",
            )

        fig.add_annotation(
            x=mark_start.isoformat(), xref="x", y=1.0, yref="paper",
            yanchor="bottom", text=mark_label or "loaded window",
            showarrow=False, font=dict(size=11, color="red"),
            bgcolor="rgba(255,255,255,0.85)", bordercolor="red", borderwidth=1,
            borderpad=3,
        )

    fig.update_layout(
        xaxis_title="Time (UTC)",
        yaxis_title="Frequency (Hz)",
        margin=dict(l=55, r=20, t=30, b=45),
        height=430,
        hovermode="closest",
    )
    return fig


# --------------------------------------------------------------------------
# the entry point app.py calls
# --------------------------------------------------------------------------
def stash_upload(upload) -> str:
    """Write an uploaded .ltsa to a temp file and return its path.

    ``LTSAFile`` memory-maps the file, so it needs a real path rather than a
    buffer. The write is skipped when the same file is already on disk, so a
    46 MB upload is not rewritten on every rerun.
    """
    target = Path(tempfile.gettempdir()) / f"ltsa_upload_{upload.name}"
    if not target.exists() or target.stat().st_size != upload.size:
        target.write_bytes(upload.getbuffer())
    return str(target)


def _heading() -> None:
    """The section title and its definition.

    Called on every path out of the panel, including the ones that never draw
    a plot: the definition is what tells a reader what an LTSA is, so it has
    to appear whether or not there is one to look at.
    """
    st.subheader("LTSA context")
    st.markdown(LTSA_DEFINITION)


def render_ltsa_panel(df: pd.DataFrame, ltsa_dir: str, opts: dict | None = None) -> None:
    """Draw the LTSA context panel for the recording held in *df*."""
    opts = opts or {}

    st.sidebar.header("LTSA context")
    if not st.sidebar.checkbox("Show LTSA", value=True):
        return

    source = df.attrs.get("source", "")
    mark_start, mark_end = marked_window(df)

    mode = st.sidebar.radio(
        "LTSA source", ["Folder", "Upload"], horizontal=True,
        label_visibility="collapsed",
    )

    # ---- upload ----------------------------------------------------------
    if mode == "Upload":
        upload = st.sidebar.file_uploader("Choose a .ltsa file", type=["ltsa"])
        if upload is None:
            _heading()
            st.info("Choose a .ltsa file in the sidebar to draw it here.")
            return
        path = stash_upload(upload)
        st.sidebar.caption(f"{upload.name} ({upload.size / 1e6:.0f} MB)")
        return _draw(df, path, source, mark_start, mark_end, opts)

    # ---- folder ----------------------------------------------------------
    # Editable, so a wrong LTSA_DIR can be fixed here instead of in the source.
    ltsa_dir = st.sidebar.text_input("LTSA folder", value=ltsa_dir)

    candidates = find_ltsa_files(ltsa_dir)
    if candidates.empty:
        # Loud, in the main area, with enough detail to fix it. Failing quietly
        # in the sidebar here just looked like the panel was broken.
        _heading()
        root = Path(ltsa_dir)

        if not root.is_dir():
            st.warning(
                f"**No such folder:** `{ltsa_dir}`\n\n"
                "Set the LTSA folder in the sidebar, switch the source to "
                "**Upload**, or change `LTSA_DIR` at the top of `app.py`."
            )
        else:
            st.warning(
                f"**No `.ltsa` files found under** `{ltsa_dir}` "
                "(searched sub-folders too)."
            )
            with st.expander("What is in that folder?"):
                entries = sorted(root.iterdir())[:40]
                if entries:
                    st.dataframe(
                        pd.DataFrame({
                            "name": [e.name for e in entries],
                            "type": ["folder" if e.is_dir() else e.suffix or "file"
                                     for e in entries],
                        }),
                        hide_index=True, width="stretch",
                    )
                else:
                    st.caption("The folder is empty.")
        return

    auto_path, reason = choose_ltsa(candidates, source)

    options = ["Auto"] + candidates["stem"].tolist()
    picked = st.sidebar.selectbox("LTSA file", options, index=0)

    if picked == "Auto":
        path = auto_path
        if path is None:
            available = ", ".join(sorted(candidates["glider"].unique())) or "none"
            _heading()
            st.info(
                f"**{source}** does not match any LTSA here. It is from glider "
                f"**{reason}**, and the LTSAs available are for: {available}. "
                "Pick one in the sidebar, or upload one, to view it anyway — "
                "but the marker is only placed when the gliders agree."
            )
            return
        st.sidebar.caption(reason)
    else:
        path = candidates.loc[candidates["stem"] == picked, "path"].iloc[0]

    return _draw(df, path, source, mark_start, mark_end, opts)


def _draw(df, path, source, mark_start, mark_end, opts) -> None:
    """Everything from opening the file to the caption, shared by both sources."""
    try:
        ltsa = open_ltsa(path, os.path.getmtime(path))
    except LTSAError as exc:
        _heading()
        st.error(f"Could not read {Path(path).name}: {exc}")
        return

    # ---- window ----------------------------------------------------------
    zoom = st.sidebar.selectbox(
        "Span", ["Whole deployment", "±1 hour", "±15 min"],
        help="How much of the LTSA to show around the loaded recording.",
    )

    if zoom == "Whole deployment" or mark_start is None:
        start, end = ltsa.times[0], ltsa.times[-1]
    else:
        pad = pd.Timedelta(hours=1) if zoom == "±1 hour" else pd.Timedelta(minutes=15)
        start = max(ltsa.times[0], mark_start - pad)
        end = min(ltsa.times[-1], (mark_end or mark_start) + pad)
        if start >= end:  # recording sits outside this LTSA entirely
            start, end = ltsa.times[0], ltsa.times[-1]

    label = dict(AVERAGING_CHOICES)[
        st.sidebar.selectbox("Averaging", [c[0] for c in AVERAGING_CHOICES], index=0)
    ]
    period = _auto_period(end - start, ltsa.tave) if label == "auto" else label

    # Default to the recording's own band so the two panels are comparable.
    wav_nyquist = float(df.attrs.get("sample_rate", 0)) / 2.0
    ceiling = float(ltsa.freq[-1])
    default_max = min(ceiling, wav_nyquist) if wav_nyquist else ceiling
    if DEFAULT_FMAX_HZ:
        default_max = min(default_max, float(DEFAULT_FMAX_HZ))
    fmax = st.sidebar.slider(
        "Max frequency (Hz)", float(ltsa.dfreq), ceiling, float(default_max),
        step=float(ltsa.dfreq) * 10,
    )

    # ---- draw ------------------------------------------------------------
    _heading()

    try:
        times, freq, psd = read_ltsa(
            path, os.path.getmtime(path), start, end, period, 0.0, float(fmax)
        )
    except LTSAError as exc:
        st.warning(str(exc))
        return

    # ---- colour bar limits ----------------------------------------------
    # Built after the read so the defaults come from the data actually on
    # screen rather than from a guess.
    auto_lo, auto_hi = auto_clim(psd)
    st.sidebar.caption(
        f"Levels on screen: {np.nanmin(psd):.0f} to {np.nanmax(psd):.0f} dB "
        f"(auto limits {auto_lo:.0f} to {auto_hi:.0f})"
    )

    if st.sidebar.checkbox(
        "Set colour limits", value=FIXED_CLIM_BY_DEFAULT,
        help="Off: limits track the 2nd-98th percentile of whatever is on "
             "screen, so they move as you change window. On: fixed values, "
             "which is what you want when comparing two recordings.",
    ):
        floor, ceiling_db = CLIM_BOUNDS
        cmax = float(st.sidebar.number_input(
            "Max (dB re 1 µPa)",
            min_value=floor, max_value=ceiling_db,
            value=float(DEFAULT_CLIM[1]), step=CLIM_STEP,
            help="Levels at or above this are drawn as the top colour.",
        ))
        cmin = float(st.sidebar.number_input(
            "Min (dB re 1 µPa)",
            min_value=floor, max_value=ceiling_db,
            value=float(DEFAULT_CLIM[0]), step=CLIM_STEP,
            help="Levels at or below this are drawn as the bottom colour.",
        ))
        if cmin >= cmax:
            st.sidebar.warning("Min must be below max — using auto limits.")
            clim = None
        else:
            clim = (cmin, cmax)
    else:
        clim = None

    # The same rule applies however this LTSA was chosen: a marker is only
    # drawn on the glider the recording actually came from. A hand-picked or
    # uploaded LTSA from another platform still gets shown, just unmarked.
    audio_glider = glider_of(source)
    ltsa_glider = glider_of(Path(path).name)
    same_glider = audio_glider.lower() == ltsa_glider.lower()

    in_view = (
        same_glider
        and mark_start is not None
        and times[0] <= mark_start <= times[-1]
    )

    fig = build_figure(
        ltsa, times, freq, psd,
        mark_start=mark_start if in_view else None,
        mark_end=mark_end if in_view else None,
        mark_label=source,
        colorscale=opts.get("colorscale", "Viridis"),
        clim=clim,
    )
    st.plotly_chart(fig, width="stretch", key="ltsa_panel",
                    config={"scrollZoom": True})

    # ---- what you are looking at ----------------------------------------
    if not same_glider:
        st.caption(
            f"No marker drawn: **{source}** is from glider **{audio_glider}**, "
            f"but this LTSA is **{ltsa_glider}**. Recordings are only placed on "
            "their own glider's LTSA — two gliders can fly the same days, so "
            "overlapping times would not mean the two belong together."
        )
    elif mark_start is None:
        st.caption(
            f"No date/time could be read from **{source}**, so the recording "
            "cannot be placed on this LTSA. Expected the date as the "
            "second-to-last underscore field (YYMMDD) and the time as the last "
            "(HHMMSS)."
        )
    elif in_view:
        st.caption(
            f"Red marks **{source}** at {mark_start:%Y-%m-%d %H:%M:%S} UTC"
            + (f" – {mark_end:%H:%M:%S}" if mark_end is not None else "")
            + f". LTSA: {Path(path).stem}, {period or f'{ltsa.tave:g} s'} averaging, "
            f"{len(times):,} time bins, colour "
            + (
                f"{clim[0]:.0f}–{clim[1]:.0f} dB (fixed)."
                if clim
                else f"{auto_lo:.0f}–{auto_hi:.0f} dB (auto)."
            )
        )
    else:
        t0, t1 = ltsa.times[0], ltsa.times[-1]
        side = "before" if mark_start < t0 else "after"
        gap = (t0 - mark_start) if mark_start < t0 else (mark_start - t1)
        st.caption(
            f"**{source}** starts {mark_start:%Y-%m-%d %H:%M:%S} UTC, which is "
            f"{gap} {side} this LTSA ({t0:%Y-%m-%d %H:%M} to {t1:%Y-%m-%d %H:%M}), "
            "so there is no marker to draw."
        )

    _render_params(ltsa, path, times, freq, psd, period, start, end, clim,
                   auto_lo, auto_hi)


def _render_params(ltsa, path, times, freq, psd, period, start, end, clim,
                   auto_lo, auto_hi) -> None:
    """How this LTSA was computed, and how this view of it was drawn.

    The standalone viewer prints these under the figure; a plot of averaged
    averages means very little without the averaging that produced it, so the
    numbers travel with the picture rather than living in the source.
    """
    left, right = st.columns(2)

    with left:
        st.markdown("**LTSA parameters**")
        st.dataframe(
            pd.DataFrame({
                "parameter": list(ltsa.params),
                "value": [str(v) for v in ltsa.params.values()],
            }),
            hide_index=True, width="stretch", height=320,
        )

    with right:
        st.markdown("**This view**")
        st.dataframe(
            pd.DataFrame({
                "parameter": [
                    "file", "window start", "window end", "window length",
                    "averaging", "time bins plotted",
                    "frequency range (Hz)", "frequency bins plotted",
                    "colour limits (dB)",
                ],
                "value": [
                    Path(path).name,
                    f"{times[0]:%Y-%m-%d %H:%M:%S}",
                    f"{times[-1]:%Y-%m-%d %H:%M:%S}",
                    str(pd.Timestamp(end) - pd.Timestamp(start)),
                    period or f"native ({ltsa.tave:g} s)",
                    f"{len(times):,}",
                    f"{freq[0]:.0f} – {freq[-1]:.0f}",
                    f"{len(freq):,}",
                    (f"{clim[0]:.0f} – {clim[1]:.0f} (fixed)" if clim
                     else f"{auto_lo:.0f} – {auto_hi:.0f} (auto)"),
                ],
            }),
            hide_index=True, width="stretch", height=320,
        )

    with st.expander(f"Source files in this LTSA ({len(ltsa.records):,})"):
        st.dataframe(ltsa.records, hide_index=True, width="stretch")

    with st.expander("Median spectrum over the plotted window"):
        st.caption(
            "The median level in each frequency bin across every time bin on "
            "screen — the shape of the background, with transients averaged out."
        )
        st.line_chart(
            pd.DataFrame({"median SPL (dB)": np.median(psd, axis=0)},
                         index=pd.Index(freq, name="Hz"))
        )
