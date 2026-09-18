"""The three Plotly figures the app shows: original, transformed, residual.

Each figure can be drawn in one of three *views*, which decide what goes on the
Y axis:

    "Waveform"     amplitude vs time      (line)
    "Spectrum"     magnitude vs frequency (line)
    "Spectrogram"  frequency vs time      (heatmap, color = level)

The view is independent of the transform: the transform decides *what* signal a
panel holds, the view decides *how* it is drawn.  Because every view puts a
single shared quantity on the X axis — time for waveform and spectrogram,
frequency for spectrum — all three panels can be linked with
:func:`link_figures` so panning or zooming one pans all of them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots

from data import channel_columns, window_span, x_column
from transformers import compute_spectrogram, fft, psd_welch

VIEWS = ("Waveform", "Spectrum", "PSD", "Spectrogram")

# Views that put frequency on the X axis, so they can draw a frame that is
# already a spectrum and cannot be linked to a time axis.
FREQUENCY_VIEWS = ("Spectrum", "PSD")

# Audio frames are far denser than a browser can draw.  Line traces are thinned
# to MAX_POINTS using a min/max envelope, which keeps the visual shape of a
# waveform intact where naive slicing would alias it away; heatmaps are block-
# reduced to at most MAX_SPEC_* bins, taking the max so transients survive.
MAX_POINTS = 4000
# Pixel height of one chain step's row of panels.
ROW_HEIGHT = 340
MAX_SPEC_TIME_BINS = 700
MAX_SPEC_FREQ_BINS = 400

DEFAULT_OPTS = {
    "window": "hann",       # spectrum: FFT window
    "scale": "dB",          # spectrum: "dB" or "linear"
    "log_x": True,          # spectrum: logarithmic frequency axis
    "psd_nperseg": 4096,    # PSD: Welch segment length
    "nperseg": 1024,        # spectrogram: FFT length
    "overlap_pct": 50.0,    # spectrogram: segment overlap
    "dynamic_range": 60.0,  # spectrogram: dB below peak to show
    "colorscale": "Viridis",
    "channel": None,        # spectrogram: which channel to draw
    "zrange": None,         # spectrogram: (zmin, zmax) shared across panels
    "residual_autoscale": False,  # let the residual pick its own color limits
}

# Power is floored at this level before the log, so a digitally silent signal
# lands at 10*log10(1e-20) = -200 dB rather than -inf.  A residual panel sitting
# flat at that floor therefore means the transform removed exactly nothing.
POWER_FLOOR_DB = 10 * np.log10(1e-20)

# Shown on hover beside any panel drawn in decibels.
DB_NOTE = (
    "<b>Reading the dB axis</b><br>"
    "<br>"
    "A decibel is not an amount of sound, it is a <i>ratio</i> on a log scale.<br>"
    "Power is turned into dB with 10&#183;log10(power), so the numbers compress<br>"
    "a huge range into a readable one:<br>"
    "<br>"
    "&nbsp;&nbsp;+3 dB &asymp; twice the power&nbsp;&nbsp;&#183;&nbsp;&nbsp;"
    "+10 dB = ten times&nbsp;&nbsp;&#183;&nbsp;&nbsp;+20 dB = a hundred times<br>"
    "<br>"
    "Exactly zero signal would be log10(0) = &minus;&infin;, which cannot be<br>"
    "plotted, so a tiny floor is added first:<br>"
    "<br>"
    "&nbsp;&nbsp;<b>10&#183;log10(power + 1e-20) = &minus;200 dB when power is 0</b><br>"
    "<br>"
    "So &minus;200 dB is not a quiet measurement, it is the floor itself: it means<br>"
    "the value was identically zero. A residual panel sitting flat at &minus;200<br>"
    "is telling you the transform removed nothing at all.<br>"
    "<br>"
    "These levels are relative to full scale (&plusmn;1.0 = the loudest the<br>"
    "recorder can store), so they are all negative and are <i>not</i> calibrated<br>"
    "sound pressure. Converting to dB re 1 &micro;Pa needs the hydrophone's<br>"
    "sensitivity and the recorder gain."
)

PALETTE = qualitative.Plotly


def _opts(overrides: dict | None) -> dict:
    return {**DEFAULT_OPTS, **(overrides or {})}


# --------------------------------------------------------------------------
# decimation helpers
# --------------------------------------------------------------------------
def _minmax_decimate(x: np.ndarray, y: np.ndarray, max_points: int = MAX_POINTS):
    """Thin a trace to ~max_points while preserving its envelope."""
    n = len(x)
    if n <= max_points:
        return x, y

    buckets = max(1, max_points // 2)
    size = n // buckets
    usable = buckets * size
    xb = x[:usable].reshape(buckets, size)
    yb = y[:usable].reshape(buckets, size)

    lo, hi = yb.argmin(axis=1), yb.argmax(axis=1)
    first, second = np.minimum(lo, hi), np.maximum(lo, hi)
    rows = np.arange(buckets)

    out_x = np.empty(buckets * 2, dtype=x.dtype)
    out_y = np.empty(buckets * 2, dtype=y.dtype)
    out_x[0::2], out_x[1::2] = xb[rows, first], xb[rows, second]
    out_y[0::2], out_y[1::2] = yb[rows, first], yb[rows, second]

    if usable < n:  # keep the tail so the axis still reaches the end
        out_x = np.append(out_x, x[-1])
        out_y = np.append(out_y, y[-1])
    return out_x, out_y


def _block_centers(values: np.ndarray, factor: int) -> np.ndarray:
    """Reduce a 1-D axis to the center coordinate of each block."""
    n = (len(values) // factor) * factor
    head = values[:n].reshape(-1, factor).mean(axis=1)
    return np.append(head, values[n:].mean()) if n < len(values) else head


def _shrink_spectrogram(f: np.ndarray, t: np.ndarray, z: np.ndarray):
    """Block-reduce a spectrogram to a browser-friendly number of cells."""
    ft = max(1, int(np.ceil(len(f) / MAX_SPEC_FREQ_BINS)))
    tt = max(1, int(np.ceil(len(t) / MAX_SPEC_TIME_BINS)))
    if ft > 1:
        n = (z.shape[0] // ft) * ft
        z = z[:n].reshape(-1, ft, z.shape[1]).max(axis=1)
        f = _block_centers(f, ft)[: z.shape[0]]
    if tt > 1:
        n = (z.shape[1] // tt) * tt
        z = z[:, :n].reshape(z.shape[0], -1, tt).max(axis=2)
        t = _block_centers(t, tt)[: z.shape[1]]
    return f, t, z


# --------------------------------------------------------------------------
# how much signal is on screen
# --------------------------------------------------------------------------
def _format_seconds(seconds: float) -> str:
    """Seconds at a precision that stays readable from milliseconds to minutes."""
    if seconds < 1.0:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 10.0:
        return f"{seconds:.3f} s"
    if seconds < 120.0:
        return f"{seconds:.2f} s"
    return f"{seconds:.1f} s ({seconds / 60:.1f} min)"


def window_label(df: pd.DataFrame, view: str = "Waveform") -> str:
    """One line describing the signal currently in memory.

    The window sliders are easy to move without seeing a result: every view
    rescales to whatever it was given, so a 1 s window and a 30 s window fill
    the same pixels and only the tick labels move.  This states the length
    outright, and in the spectrum view adds the frequency resolution it buys —
    Δf = 1/T is the one number a longer window visibly changes there.
    """
    span = window_span(df)
    if span["duration_s"] <= 0:
        return ""

    parts = [
        f"Loaded {_format_seconds(span['duration_s'])}",
        f"{span['start_s']:.2f}–{span['end_s']:.2f} s of the file",
    ]
    if span["n_samples"]:
        parts.append(f"{span['n_samples']:,} samples/ch")
    if span["sample_rate"]:
        parts.append(f"{span['sample_rate']:,.0f} Hz")
    if view == "Spectrum":
        parts.append(f"Δf = {1.0 / span['duration_s']:.3g} Hz")
    return " · ".join(parts)


def _pin_to_window(fig: go.Figure, df: pd.DataFrame) -> go.Figure:
    """Fix a time axis to exactly the loaded window.

    Without this the X axis autoranges to the data with padding, so the panel
    looks much the same whatever the window length.  The loaded span is the
    thing being shown, so it sets the axis rather than the other way round —
    and a double-click now resets to the window, not to the traces.
    """
    span = window_span(df)
    if span["duration_s"] > 0:
        fig.update_xaxes(range=[span["start_s"], span["end_s"]])
    return fig


# --------------------------------------------------------------------------
# view renderers — each returns a complete, standalone figure
# --------------------------------------------------------------------------
def _base_layout(fig: go.Figure, title: str, x_label: str, y_label: str) -> go.Figure:
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        margin=dict(l=55, r=20, t=50, b=45),
        height=430,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0),
    )
    return fig


def _line_traces(fig: go.Figure, df: pd.DataFrame, xcol: str) -> None:
    """One decimated line per channel, colored consistently across panels."""
    x = df[xcol].to_numpy(dtype=np.float64)
    for i, col in enumerate(channel_columns(df)):
        xs, ys = _minmax_decimate(x, df[col].to_numpy(dtype=np.float64))
        fig.add_trace(
            go.Scattergl(
                x=xs, y=ys, mode="lines", name=col, legendgroup=col,
                line=dict(width=1, color=PALETTE[i % len(PALETTE)]),
            )
        )


def _render_waveform(df: pd.DataFrame, title: str, opts: dict) -> go.Figure:
    fig = go.Figure()
    _line_traces(fig, df, x_column(df))
    _base_layout(
        fig, title, df.attrs.get("x_label", "Time (s)"),
        df.attrs.get("y_label", "Amplitude"),
    )
    return _pin_to_window(fig, df) if df.attrs.get("domain") == "time" else fig


def _render_spectrum(df: pd.DataFrame, title: str, opts: dict) -> go.Figure:
    """Frequency spectrum.  Frames that are already spectra are drawn as-is."""
    spec = df if df.attrs.get("domain") == "frequency" else fft(
        df, window=opts["window"], scale=opts["scale"], detrend=True
    )
    fig = go.Figure()
    _line_traces(fig, spec, x_column(spec))
    _base_layout(
        fig, title, spec.attrs.get("x_label", "Frequency (Hz)"),
        spec.attrs.get("y_label", "Magnitude"),
    )
    return _log_frequency_axis(fig, spec, opts)


def _log_frequency_axis(fig: go.Figure, spec: pd.DataFrame, opts: dict) -> go.Figure:
    """Switch a spectrum panel to a log frequency axis when asked."""
    if not opts["log_x"]:
        return fig
    # A log axis cannot show the DC bin; start at the first non-zero line.
    freqs = spec[x_column(spec)].to_numpy()
    positive = freqs[freqs > 0]
    fig.update_xaxes(type="log")
    if positive.size:
        fig.update_xaxes(range=[np.log10(positive[0]), np.log10(freqs[-1])])
    return fig


def _render_psd(df: pd.DataFrame, title: str, opts: dict) -> go.Figure:
    """Welch power spectral density.

    The same axes as the spectrum view, but averaged over overlapping segments:
    a single FFT of a noisy recording is itself noisy, and averaging trades the
    fine frequency detail it does have for an estimate steady enough to compare
    one panel against another.  Frames that are already spectra are drawn as-is.
    """
    if df.attrs.get("domain") == "frequency":
        spec = df
    else:
        spec = psd_welch(
            df,
            nperseg=int(min(opts["psd_nperseg"], max(16, len(df)))),
            overlap_pct=opts["overlap_pct"],
            scale=opts["scale"],
        )
    fig = go.Figure()
    _line_traces(fig, spec, x_column(spec))
    _base_layout(
        fig, title, spec.attrs.get("x_label", "Frequency (Hz)"),
        spec.attrs.get("y_label", "PSD"),
    )
    return _log_frequency_axis(fig, spec, opts)


def _render_spectrogram(df: pd.DataFrame, title: str, opts: dict) -> go.Figure:
    if df.attrs.get("domain") != "time":
        return _message_figure(
            title, "A spectrogram needs a time-domain signal,<br>"
                   "but this panel already holds a spectrum."
        )

    channels = channel_columns(df)
    channel = opts["channel"] if opts["channel"] in channels else channels[0]
    f, t, z = compute_spectrogram(
        df, channel, nperseg=opts["nperseg"], overlap_pct=opts["overlap_pct"]
    )
    f, t, z = _shrink_spectrogram(f, t, z)

    if opts["zrange"] is not None:
        zmin, zmax = opts["zrange"]
    else:
        zmax = float(np.nanmax(z))
        zmin = zmax - float(opts["dynamic_range"])

    fig = go.Figure(
        go.Heatmap(
            x=t, y=f, z=np.round(z, 1).astype(np.float32), zmin=zmin, zmax=zmax,
            colorscale=opts["colorscale"], zsmooth=False,
            colorbar=dict(title="dB", thickness=12),
            hovertemplate="t=%{x:.3f}s<br>f=%{y:.0f}Hz<br>%{z:.1f} dB<extra></extra>",
        )
    )
    _base_layout(fig, f"{title} · {channel}", "Time (s)", "Frequency (Hz)")
    fig.update_layout(hovermode="closest")
    # Frequency is the whole point of this view, so the axis opens on the whole
    # band.  Plotly still lets a zoom of your own outlive a redraw: a supplied
    # autorange only takes effect when the axis's uirevision has moved on.
    fig.update_yaxes(autorange=True)
    return _pin_to_window(fig, df)


_RENDERERS = {
    "Waveform": _render_waveform,
    "Spectrum": _render_spectrum,
    "PSD": _render_psd,
    "Spectrogram": _render_spectrogram,
}


def _render(df: pd.DataFrame, view: str, title: str, opts: dict | None) -> go.Figure:
    if view not in _RENDERERS:
        raise ValueError(f"unknown view: {view!r} (expected one of {VIEWS})")
    # A frame that is already a spectrum has no time axis to draw on, so the
    # waveform view falls back to showing it for what it is.  The spectrogram
    # renderer says so itself, with a placeholder.
    if view == "Waveform" and df.attrs.get("domain") == "frequency":
        view = "Spectrum"
    return _RENDERERS[view](df, title, _opts(opts))


def _message_figure(title: str, message: str) -> go.Figure:
    """Placeholder used when a panel cannot be drawn in the requested view."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
        align="center", font=dict(size=13),
    )
    fig.update_layout(
        title=title, height=430, margin=dict(l=55, r=20, t=50, b=45),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        meta=dict(placeholder=True, message=message),
    )
    return fig


# --------------------------------------------------------------------------
# the three public figures
# --------------------------------------------------------------------------
def plot_original(df: pd.DataFrame, view: str = "Waveform", opts: dict | None = None,
                  title: str | None = None):
    """Column 1 — what went into this step, drawn in *view*."""
    src = df.attrs.get("source", "")
    return _render(df, view, title or f"Input{f' · {src}' if src else ''}", opts)


def plot_transformed(df: pd.DataFrame, view: str = "Waveform", opts: dict | None = None,
                     title: str | None = None):
    """Column 2 — what this step produced, drawn in *view*."""
    return _render(
        df, view, title or f"Output · {df.attrs.get('transform', 'Transformed')}", opts
    )


def _spectral_difference(
    original_df: pd.DataFrame, transformed_df: pd.DataFrame, opts: dict | None,
    title: str | None = None,
) -> go.Figure:
    """Residual for a transform whose output is already a spectrum.

    FFT and Welch PSD do not remove anything from the signal, they re-express
    it, so the comparison has to happen in the frequency domain: the input's
    spectrum is computed with the same magnitude scale as the output, then
    interpolated onto the output's frequency grid before subtracting.

    For a plain FFT the two sides agree and the residual is flat zero — the
    same sanity check Passthrough gives in the time domain.  For Welch PSD the
    two sides are different estimators and PSD carries a per-Hz normalization,
    so read that result as a level offset between representations rather than
    as energy the transform removed.
    """
    o = _opts(opts)
    scale = "dB" if "dB" in (transformed_df.attrs.get("y_label") or "") else "linear"
    reference = fft(original_df, window=o["window"], scale=scale, detrend=True)

    shared = [c for c in channel_columns(reference) if c in transformed_df.columns]
    if not shared:
        return _message_figure("Residual · unavailable", "No channels in common.")

    fcol = x_column(transformed_df)
    freqs = transformed_df[fcol].to_numpy(dtype=np.float64)
    ref_freqs = reference[x_column(reference)].to_numpy(dtype=np.float64)

    out = pd.DataFrame({fcol: freqs})
    for col in shared:
        ref = np.interp(freqs, ref_freqs, reference[col].to_numpy(dtype=np.float64))
        out[col] = ref - transformed_df[col].to_numpy(dtype=np.float64)

    unit = "dB" if scale == "dB" else "linear"
    out.attrs = {**transformed_df.attrs, "y_label": "Δ level (%s)" % unit}
    heading = title or "Residual · input − output (spectra)"
    return _render(out, "Spectrum", _zero_suffix(out, shared, heading), opts)


def _zero_suffix(df: pd.DataFrame, cols: list[str], title: str) -> str:
    """Flag an exactly-zero residual in the panel title.

    Worth calling out because a zero residual is invisible in some views: as a
    spectrogram it is a flat field at the power floor, which reads as data
    until you check the color bar.
    """
    if np.all(df[cols].to_numpy() == 0):
        return "%s ≡ 0" % title
    return title


def plot_difference(
    original_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
    view: str = "Waveform",
    opts: dict | None = None,
    title: str | None = None,
) -> go.Figure:
    """Column 3 — the residual, input minus output, drawn in *view*.

    The residual is always formed on the *signals* and only then rendered, so
    the spectrum view shows the spectrum of what the transform removed rather
    than a difference of two spectra.  The two frames are aligned on their
    shared axis: identical grids subtract directly, differing grids (e.g. after
    decimation) are linearly interpolated onto the original's axis first.  When
    the transform's output is already a spectrum there is no signal-domain
    residual to take, so the comparison moves to the frequency domain — see
    :func:`_spectral_difference`.
    """
    xcol, tcol = x_column(original_df), x_column(transformed_df)
    in_domain = original_df.attrs.get("domain")
    out_domain = transformed_df.attrs.get("domain")

    if in_domain == "time" and out_domain == "frequency":
        return _spectral_difference(original_df, transformed_df, opts, title)

    if xcol != tcol or in_domain != out_domain:
        return _message_figure(
            title or "Residual · unavailable",
            "Input and output are in different domains<br>"
            f"({in_domain or '?'} vs {out_domain or '?'}),<br>"
            "so input − output is not defined.",
        )

    shared = [c for c in channel_columns(original_df) if c in transformed_df.columns]
    if not shared:
        return _message_figure(
            title or "Residual · unavailable", "No channels in common."
        )

    x = original_df[xcol].to_numpy(dtype=np.float64)
    xt = transformed_df[tcol].to_numpy(dtype=np.float64)
    resampled = len(x) != len(xt) or not np.allclose(x, xt)

    out = pd.DataFrame({xcol: x})
    for col in shared:
        y_out = transformed_df[col].to_numpy(dtype=np.float64)
        if resampled:
            y_out = np.interp(x, xt, y_out)
        out[col] = original_df[col].to_numpy(dtype=np.float64) - y_out

    out.attrs = {**original_df.attrs}
    if view == "Waveform":
        out.attrs["y_label"] = f"Δ {original_df.attrs.get('y_label', 'Amplitude')}"
    heading = title or "Residual · input − output"
    if resampled:
        heading += " (interpolated)"
    return _render(out, view, _zero_suffix(out, shared, heading), opts)


# --------------------------------------------------------------------------
# linking
# --------------------------------------------------------------------------
def axis_revisions(
    df: pd.DataFrame,
    view: str,
    opts: dict | None = None,
    transform_key: str = "",
    shape: str = "",
) -> tuple[str, str]:
    """Revision tokens that decide when a zoom is kept and when it is dropped.

    Plotly keeps the user's pan/zoom across a redraw for as long as an axis's
    ``uirevision`` token is unchanged, so the token has to encode everything
    that would make an old range meaningless.  The rule is that an axis stays
    put while the quantity on it stays the same:

    * X is sticky across transform changes — that is the point: switching
      Passthrough to Low-pass keeps the time span you were looking at.  It
      resets when the axis stops meaning the same thing: a different file or
      window, or a view that swaps time for frequency.
    * Y follows the data where the data sets the scale.  Amplitude and
      magnitude are rescaled by the transform, so those reset with it; the
      frequency axis of a spectrogram is not, so it stays put like X.

    *shape* is the size of the matrix, and both tokens carry it.  Axes are
    numbered down the grid, so adding or removing a step renumbers them: axis 5
    was a residual's magnitude a moment ago and is a frequency axis now.  Those
    are different quantities wearing the same name, and without the shape in
    the token Plotly would restore the old range onto the new axis — which is
    how a spectrogram ends up opening on a 4 Hz sliver of its band.
    """
    o = _opts(opts)
    window = (f"{df.attrs.get('source', '')}|{df.attrs.get('start_s', 0)}"
              f"|{len(df)}|{shape}")

    if view in FREQUENCY_VIEWS:
        # A log axis stores its range as powers of ten; a linear one does not.
        return (f"{window}|freq|log={o['log_x']}",
                f"{window}|mag|{view}|{o['scale']}|{transform_key}")
    if view == "Spectrogram":
        return f"{window}|time", f"{window}|freq|{df.attrs.get('sample_rate')}"
    return f"{window}|time", f"{window}|amp|{transform_key}"


def spectrogram_range(fig: go.Figure) -> tuple[float, float] | None:
    """Color limits of a rendered spectrogram, for reuse on another panel.

    Sharing the input panel's limits with the output panel is what makes the
    two comparable — if each self-scaled, a low-pass output would look just as
    bright as its input.  Returns ``None`` for any other view.
    """
    for trace in fig.data:
        if isinstance(trace, go.Heatmap):
            return float(trace.zmin), float(trace.zmax)
    return None


def _uses_db(figures: list[go.Figure]) -> bool:
    """True when any panel is drawn on a decibel scale.

    Detected from what was actually rendered — a dB axis title or a heatmap,
    which is always a power spectrogram here — so the reminder follows the
    views that need it without anything having to declare it.
    """
    for fig in figures:
        if "dB" in (fig.layout.yaxis.title.text or ""):
            return True
        if any(isinstance(trace, go.Heatmap) for trace in fig.data):
            return True
    return False


def _axis_key(index: int, letter: str = "x") -> str:
    return f"{letter}axis" if index == 1 else f"{letter}axis{index}"


def _x_signature(fig: go.Figure) -> tuple:
    """What a panel's X axis *means*, so only like axes get linked.

    Time and frequency both end up on the X axis depending on the view, and a
    chain can mix them: an FFT step hands on a spectrum while the rows above it
    are still in seconds.  Linking those would tie a 5 s span to a 96 kHz one.
    """
    axis = fig.layout.xaxis
    return (axis.title.text or "", axis.type or "linear")


def _y_signature(fig: go.Figure) -> tuple:
    axis = fig.layout.yaxis
    return (axis.title.text or "", axis.type or "linear")


def _axis_ref(index: int, letter: str = "x") -> str:
    """The name an axis is referred to by ``matches`` (``x``, ``x2``, …)."""
    return letter if index == 1 else f"{letter}{index}"


def link_grid(
    rows: list[dict],
    link_x: bool = True,
    link_y: bool = False,
    x_revision: str | None = None,
    y_revision: str | None = None,
    window_note: str | None = None,
    row_height: int = ROW_HEIGHT,
    horizontal_spacing: float = 0.055,
) -> go.Figure:
    """Combine a matrix of panels into one figure whose X axes move together.

    *rows* is what :func:`chain_figures` returns: one ``{"label", "figures"}``
    per chain step, each holding the three panels of that step — input, output,
    residual.  Plotly only synchronizes axes inside a single figure, so the
    whole matrix is built as one subplot grid and every compatible axis is
    given ``matches``, which is what lets a zoom on step 3's residual pan the
    original input two rows above it.

    Only *compatible* axes are linked (see :func:`_x_signature`), so a step
    that turns the signal into a spectrum keeps its own frequency axis instead
    of being dragged along by the time axes around it.

    Pass the tokens from :func:`axis_revisions` as *x_revision* / *y_revision*
    to carry the current zoom across a redraw, and :func:`window_label` as
    *window_note* to caption the matrix with how much signal it holds.
    """
    grid = [row["figures"] for row in rows]
    n_rows, n_cols = len(grid), max(len(r) for r in grid)
    flat = [fig for row in grid for fig in row]
    placeholder = [bool((f.layout.meta or {}).get("placeholder")) for f in flat]

    shows_db = _uses_db(flat)
    top = 86 if (window_note or shows_db) else 60
    bottom = 60
    height = n_rows * row_height + top + bottom
    plot_area = max(1.0, height - top - bottom)
    # Subplot titles need a constant *pixel* gap between rows, which is a
    # shrinking fraction of a grid that grows taller with every step added.
    v_space = min(0.9 / (n_rows - 1), 58.0 / plot_area) if n_rows > 1 else 0.0

    sub = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=[f.layout.title.text or "" for f in flat],
        horizontal_spacing=horizontal_spacing, vertical_spacing=v_space,
    )

    # The first drawable panel anchors every axis that means the same thing.
    ref_idx = next((i for i, ph in enumerate(placeholder, start=1) if not ph), None)
    ref_fig = flat[ref_idx - 1] if ref_idx else None

    max_slots = 0
    for r, row in enumerate(grid, start=1):
        # Colour limits are shared within a row (input and output are only
        # comparable on one scale), so the row carries one colour bar — two
        # only when the residual has been let off onto its own limits.
        slots: list[tuple] = []
        shown: set[tuple] = set()

        for c, fig in enumerate(row, start=1):
            idx = (r - 1) * n_cols + c
            is_ph = placeholder[idx - 1]

            for trace in fig.data:
                trace = trace.__class__(trace)  # copy: leave the source usable
                if isinstance(trace, go.Heatmap):
                    key = (round(float(trace.zmin), 3), round(float(trace.zmax), 3))
                    if key not in slots:
                        slots.append(key)
                    # One bar per distinct scale: three identical bars per row
                    # would cost more width than they explain.
                    trace.showscale = key not in shown
                    if trace.showscale:
                        shown.add(key)
                        trace.colorbar = dict(
                            x=1.004 + slots.index(key) * 0.032, xanchor="left",
                            y=_row_center(sub, idx), yanchor="middle",
                            len=_row_len(sub, idx), thickness=9,
                            title=dict(text="dB", side="right"),
                            tickfont=dict(size=9),
                        )
                else:
                    trace.showlegend = idx == (ref_idx or 1)
                sub.add_trace(trace, row=r, col=c)

            x_axis, y_axis = fig.layout.xaxis, fig.layout.yaxis
            sub.update_xaxes(
                # Only the bottom row is labelled: the axis is the same all the
                # way up, and a title per row would cost a line of every panel.
                title_text=x_axis.title.text if r == n_rows else None,
                type=x_axis.type, uirevision=x_revision, row=r, col=c,
            )
            sub.update_yaxes(title_text=y_axis.title.text, type=y_axis.type,
                             uirevision=y_revision, row=r, col=c)
            if y_axis.autorange is not None:
                sub.update_yaxes(autorange=y_axis.autorange, row=r, col=c)

            matched = False
            if ref_fig is not None and not is_ph and idx != ref_idx:
                if link_x and _x_signature(fig) == _x_signature(ref_fig):
                    sub.layout[_axis_key(idx)].matches = _axis_ref(ref_idx)
                    matched = True
                if link_y and _y_signature(fig) == _y_signature(ref_fig):
                    sub.layout[_axis_key(idx, "y")].matches = _axis_ref(ref_idx, "y")
            # A matched axis takes its range from the anchor, so setting one
            # here would be quietly ignored.
            if x_axis.range is not None and not matched:
                sub.update_xaxes(range=list(x_axis.range), row=r, col=c)

            if is_ph:
                sub.add_annotation(
                    x=_col_center(sub, idx), y=_row_center(sub, idx),
                    xref="paper", yref="paper", showarrow=False, align="center",
                    font=dict(size=12),
                    text=(fig.layout.meta or {}).get("message", ""),
                )
                sub.update_xaxes(visible=False, row=r, col=c)
                sub.update_yaxes(visible=False, row=r, col=c)

        max_slots = max(max_slots, len(slots))

    note_y = 1.0 + 34.0 / plot_area
    if window_note:
        # One window feeds every panel, so it is stated once for the matrix.
        sub.add_annotation(
            x=0.0, y=note_y, xref="paper", yref="paper",
            xanchor="left", yanchor="bottom", text=window_note, showarrow=False,
            font=dict(size=11, color="#374151"),
        )
    if shows_db:
        # A hover chip rather than visible text: the explanation is long, and it
        # is a reminder for when the axis looks odd, not something to read every
        # time. Sits top-right on the window note's row, above the legend.
        sub.add_annotation(
            x=1.0, y=note_y, xref="paper", yref="paper",
            xanchor="right", yanchor="bottom",
            text="ⓘ what does dB mean?", showarrow=False,
            font=dict(size=11, color="#6b7280"),
            bordercolor="#c8cdd4", borderwidth=1, borderpad=4,
            hovertext=DB_NOTE,
            hoverlabel=dict(bgcolor="#ffffff", bordercolor="#c8cdd4",
                            font=dict(size=12, color="#111827")),
        )

    # Subplot titles only — the note and the dB chip set their own size below.
    for ann in sub.layout.annotations[: n_rows * n_cols]:
        ann.font = dict(size=12)

    sub.update_layout(
        # Governs non-axis UI state (which channels are toggled off in the
        # legend); the per-axis tokens above override it for ranges.
        uirevision=x_revision or True,
        height=height,
        margin=dict(l=62, r=30 + 44 * max_slots, t=top, b=bottom),
        hovermode=flat[0].layout.hovermode or "x unified",
        legend=dict(orientation="h", yanchor="bottom", y=note_y - 0.005,
                    xanchor="right", x=0.88),
    )
    return sub


def _row_center(sub: go.Figure, idx: int) -> float:
    domain = sub.layout[_axis_key(idx, "y")].domain
    return (domain[0] + domain[1]) / 2.0


def _row_len(sub: go.Figure, idx: int) -> float:
    domain = sub.layout[_axis_key(idx, "y")].domain
    return float(domain[1] - domain[0])


def _col_center(sub: go.Figure, idx: int) -> float:
    domain = sub.layout[_axis_key(idx)].domain
    return (domain[0] + domain[1]) / 2.0


# --------------------------------------------------------------------------
# the chain as a matrix of panels
# --------------------------------------------------------------------------
def chain_figures(
    stages,
    view: str = "Waveform",
    opts: dict | None = None,
    cumulative: bool = True,
) -> list[dict]:
    """Turn the chain into rows of panels, one per step.

    Each row reads left to right: what reached this step, what it produced, and
    the difference between the two — so the residual always answers "what did
    *this* step change", not "how far are we from the recording".

    A chain of two or more steps gets a closing **cumulative** row, which does
    ask the other question: the original file against the final output, with
    everything the chain removed on the right.
    """
    rows = [_stage_row(stage, view, opts) for stage in stages]
    if cumulative and len(stages) >= 2:
        rows.append(_cumulative_row(stages, view, opts))
    return rows


def _stage_row(stage, view: str, opts: dict | None) -> dict:
    """The three panels for one step of the chain."""
    label = stage.label

    if stage.source is None:
        message = stage.error or "this step did not run"
        return {
            "label": label,
            "figures": [
                _message_figure(f"{label} · {what}", message)
                for what in ("in", "out", "removed")
            ],
        }

    fig_in = plot_original(
        stage.source, view, opts, title=f"{label} · in ← {stage.source_label}"
    )
    if stage.result is None:
        message = stage.error or "this step failed"
        return {
            "label": label,
            "figures": [
                fig_in,
                _message_figure(f"{label} · out", message),
                _message_figure(f"{label} · removed", "no output to compare against"),
            ],
        }

    o = _opts(opts)
    # Reuse this row's input colour limits on its output so the two compare.
    shared = {**o, "zrange": spectrogram_range(fig_in)}
    fig_out = plot_transformed(stage.result, view, shared, title=f"{label} · out")
    fig_res = plot_difference(
        stage.source, stage.result, view,
        o if o["residual_autoscale"] else shared,
        title=f"{label} · removed (in − out)",
    )
    return {"label": label, "figures": [fig_in, fig_out, fig_res]}


def _cumulative_row(stages, view: str, opts: dict | None) -> dict:
    """Original input against the chain's final output."""
    label = "Σ Cumulative"
    source = stages[0].source
    last = next((s for s in reversed(stages) if s.ok), None)

    if source is None or last is None:
        return {
            "label": label,
            "figures": [
                _message_figure(f"{label} · {what}", "the chain produced no output")
                for what in ("original", "final", "removed")
            ],
        }

    fig_in = plot_original(
        source, view, opts,
        title=f"{label} · original ← {stages[0].source_label}",
    )
    o = _opts(opts)
    shared = {**o, "zrange": spectrogram_range(fig_in)}
    fig_out = plot_transformed(
        last.result, view, shared, title=f"{label} · final ← {last.label}"
    )
    fig_res = plot_difference(
        source, last.result, view,
        o if o["residual_autoscale"] else shared,
        title=f"{label} · removed by the whole chain",
    )
    return {"label": label, "figures": [fig_in, fig_out, fig_res]}
