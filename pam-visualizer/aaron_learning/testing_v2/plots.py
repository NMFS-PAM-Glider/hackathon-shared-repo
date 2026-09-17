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
from transformers import compute_spectrogram, fft

VIEWS = ("Waveform", "Spectrum", "Spectrogram")

# Audio frames are far denser than a browser can draw.  Line traces are thinned
# to MAX_POINTS using a min/max envelope, which keeps the visual shape of a
# waveform intact where naive slicing would alias it away; heatmaps are block-
# reduced to at most MAX_SPEC_* bins, taking the max so transients survive.
MAX_POINTS = 4000
MAX_SPEC_TIME_BINS = 700
MAX_SPEC_FREQ_BINS = 400

DEFAULT_OPTS = {
    "window": "hann",       # spectrum: FFT window
    "scale": "dB",          # spectrum: "dB" or "linear"
    "log_x": True,          # spectrum: logarithmic frequency axis
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
    if opts["log_x"]:
        # A log axis cannot show the DC bin; start at the first non-zero line.
        freqs = spec[x_column(spec)].to_numpy()
        positive = freqs[freqs > 0]
        fig.update_xaxes(type="log")
        if positive.size:
            fig.update_xaxes(range=[np.log10(positive[0]), np.log10(freqs[-1])])
    return fig


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
    return _pin_to_window(fig, df)


_RENDERERS = {
    "Waveform": _render_waveform,
    "Spectrum": _render_spectrum,
    "Spectrogram": _render_spectrogram,
}


def _render(df: pd.DataFrame, view: str, title: str, opts: dict | None) -> go.Figure:
    try:
        return _RENDERERS[view](df, title, _opts(opts))
    except KeyError:
        raise ValueError(f"unknown view: {view!r} (expected one of {VIEWS})") from None


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
def plot_original(df: pd.DataFrame, view: str = "Waveform", opts: dict | None = None):
    """Figure 1 — the input data as loaded, drawn in *view*."""
    src = df.attrs.get("source", "")
    return _render(df, view, f"Input{f' · {src}' if src else ''}", opts)


def plot_transformed(df: pd.DataFrame, view: str = "Waveform", opts: dict | None = None):
    """Figure 2 — the output of the selected transform, drawn in *view*."""
    return _render(df, view, f"Output · {df.attrs.get('transform', 'Transformed')}", opts)


def _spectral_difference(
    original_df: pd.DataFrame, transformed_df: pd.DataFrame, opts: dict | None
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
    title = "Residual · input − output (spectra)"
    return _render(out, "Spectrum", _zero_suffix(out, shared, title), opts)


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
) -> go.Figure:
    """Figure 3 — the residual, input minus output, drawn in *view*.

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
        return _spectral_difference(original_df, transformed_df, opts)

    if xcol != tcol or in_domain != out_domain:
        return _message_figure(
            "Residual · unavailable",
            "Input and output are in different domains<br>"
            f"({in_domain or '?'} vs {out_domain or '?'}),<br>"
            "so input − output is not defined.",
        )

    shared = [c for c in channel_columns(original_df) if c in transformed_df.columns]
    if not shared:
        return _message_figure("Residual · unavailable", "No channels in common.")

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
    title = "Residual · input − output" + (" (interpolated)" if resampled else "")
    return _render(out, view, _zero_suffix(out, shared, title), opts)


# --------------------------------------------------------------------------
# linking
# --------------------------------------------------------------------------
def axis_revisions(
    df: pd.DataFrame,
    view: str,
    opts: dict | None = None,
    transform_key: str = "",
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
    """
    o = _opts(opts)
    window = f"{df.attrs.get('source', '')}|{df.attrs.get('start_s', 0)}|{len(df)}"

    if view == "Spectrum":
        # A log axis stores its range as powers of ten; a linear one does not.
        return f"{window}|freq|log={o['log_x']}", f"{window}|mag|{o['scale']}|{transform_key}"
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


def link_figures(
    figures: list[go.Figure],
    link_x: bool = True,
    link_y: bool = False,
    x_revision: str | None = None,
    y_revision: str | None = None,
    window_note: str | None = None,
    horizontal_spacing: float = 0.055,
) -> go.Figure:
    """Combine panels into one figure whose X axes pan and zoom together.

    Plotly only synchronizes axes that live in the same figure, so the panels
    are merged into a 1-row subplot grid and every axis after the first is given
    ``matches="x"``.  Panels holding a placeholder are left unlinked, since they
    have no data and no comparable axis.

    Pass the tokens from :func:`axis_revisions` as *x_revision* / *y_revision*
    to carry the current zoom across a redraw, and :func:`window_label` as
    *window_note* to caption the panels with how much signal they hold.
    """
    titles = [f.layout.title.text or "" for f in figures]
    sub = make_subplots(
        rows=1, cols=len(figures), subplot_titles=titles,
        horizontal_spacing=horizontal_spacing,
    )
    placeholder = [bool((f.layout.meta or {}).get("placeholder")) for f in figures]
    has_heatmap = False

    for i, fig in enumerate(figures, start=1):
        domain = sub.layout[_axis_key(i)].domain
        center = (domain[0] + domain[1]) / 2.0

        for trace in fig.data:
            trace = trace.__class__(trace)  # copy so the source figure stays usable
            if isinstance(trace, go.Heatmap):
                has_heatmap = True
                # Horizontal colorbar under this panel; a vertical one would sit
                # on top of the neighbouring subplot.
                trace.colorbar = dict(
                    orientation="h", x=center, xanchor="center", y=-0.22,
                    yanchor="top", len=domain[1] - domain[0], thickness=10,
                    title=dict(text="dB", side="right"),
                )
            else:
                trace.showlegend = i == 1
            sub.add_trace(trace, row=1, col=i)

        x_axis, y_axis = fig.layout.xaxis, fig.layout.yaxis
        sub.update_xaxes(title_text=x_axis.title.text, type=x_axis.type,
                         uirevision=x_revision, row=1, col=i)
        sub.update_yaxes(title_text=y_axis.title.text, type=y_axis.type,
                         uirevision=y_revision, row=1, col=i)
        if x_axis.range is not None:
            sub.update_xaxes(range=list(x_axis.range), row=1, col=i)

        if placeholder[i - 1]:
            sub.add_annotation(
                x=center, y=0.5, xref="paper", yref="paper", showarrow=False,
                align="center", font=dict(size=13),
                text=(fig.layout.meta or {}).get("message", ""),
            )
            sub.update_xaxes(visible=False, row=1, col=i)
            sub.update_yaxes(visible=False, row=1, col=i)

    for i in range(2, len(figures) + 1):
        if placeholder[i - 1] or placeholder[0]:
            continue
        if link_x:
            sub.layout[_axis_key(i)].matches = "x"
        if link_y:
            sub.layout[_axis_key(i, "y")].matches = "y"

    if window_note:
        # The three panels always share one window, so it is stated once, above
        # them all, rather than repeated in each subplot title.
        sub.add_annotation(
            x=0.0, y=1.13, xref="paper", yref="paper",
            xanchor="left", yanchor="bottom",
            text=window_note, showarrow=False,
            font=dict(size=11, color="#374151"),
        )

    shows_db = _uses_db(figures)
    if shows_db:
        # A hover chip rather than visible text: the explanation is long, and it
        # is a reminder for when the axis looks odd, not something to read every
        # time. Sits top-right on the window note's row, above the legend.
        sub.add_annotation(
            x=1.0, y=1.13, xref="paper", yref="paper",
            xanchor="right", yanchor="bottom",
            text="\u24d8 what does dB mean?", showarrow=False,
            font=dict(size=11, color="#6b7280"),
            bordercolor="#c8cdd4", borderwidth=1, borderpad=4,
            hovertext=DB_NOTE,
            hoverlabel=dict(bgcolor="#ffffff", bordercolor="#c8cdd4",
                            font=dict(size=12, color="#111827")),
        )

    sub.update_layout(
        # Governs non-axis UI state (which channels are toggled off in the
        # legend); the per-axis tokens above override it for ranges.
        uirevision=x_revision or True,
        height=470,
        margin=dict(
            l=55, r=20,
            t=80 if (shows_db or window_note) else 55,
            b=110 if has_heatmap else 50,
        ),
        hovermode=figures[0].layout.hovermode or "x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
    )
    return sub
