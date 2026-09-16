"""Template transform functions plus the registry that populates the app's menu.

Adding a new transform is two steps:

1. Write a function ``def my_transform(df, param1, param2=...)`` that takes a
   DataFrame in this package's convention (see ``data.py``) and returns a new
   DataFrame in the same convention.  Use :func:`carry_attrs` to keep the
   metadata, overriding whatever the transform changed.
2. Add one ``Transform(...)`` entry to :data:`TRANSFORMS`.  The ``params`` list
   is what ``app.py`` turns into sidebar widgets, so no UI code is needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
from scipy import signal

from data import carry_attrs, channel_columns, x_column


# --------------------------------------------------------------------------
# registry plumbing
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Param:
    """One tunable argument of a transform, rendered as a sidebar widget.

    ``kind`` is one of "float", "int", "choice" or "bool".  Set
    ``max_from="nyquist"`` on a frequency parameter to have the app clamp its
    upper bound to the current recording's Nyquist frequency.
    """

    name: str
    label: str
    kind: str
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: Sequence[Any] = ()
    max_from: str | None = None
    help: str = ""


@dataclass(frozen=True)
class Transform:
    func: Callable[..., pd.DataFrame]
    description: str
    domain: str = "time"  # domain of the *output* frame
    params: list[Param] = field(default_factory=list)


def _nyquist(df: pd.DataFrame) -> float:
    return df.attrs.get("sample_rate", 2.0) / 2.0


def _sos_filter(df: pd.DataFrame, sos) -> pd.DataFrame:
    """Apply a zero-phase SOS filter to every channel, preserving the axis."""
    out = df.copy()
    for col in channel_columns(df):
        out[col] = signal.sosfiltfilt(sos, df[col].to_numpy(dtype=np.float64))
    return carry_attrs(out, df)


# --------------------------------------------------------------------------
# transforms — time domain in, time domain out
# --------------------------------------------------------------------------
def _odd(n: int) -> int:
    """Round a window length up to the next odd number.

    A centered rolling window can only be truly symmetric when it spans an odd
    number of samples; pandas resolves an even window by leaning half a sample
    to one side, which shows up as a constant +0.5-sample lag. Forcing odd
    keeps these smoothers strictly zero-phase.
    """
    n = max(1, int(n))
    return n + 1 if n % 2 == 0 else n


def passthrough(df: pd.DataFrame) -> pd.DataFrame:
    """Return the input unchanged (useful as a residual sanity check)."""
    return carry_attrs(df.copy(), df)


def lowpass(df: pd.DataFrame, cutoff_hz: float = 1000.0, order: int = 4) -> pd.DataFrame:
    """Zero-phase Butterworth low-pass."""
    wn = min(cutoff_hz, _nyquist(df) * 0.99) / _nyquist(df)
    return _sos_filter(df, signal.butter(order, wn, btype="lowpass", output="sos"))


def highpass(df: pd.DataFrame, cutoff_hz: float = 100.0, order: int = 4) -> pd.DataFrame:
    """Zero-phase Butterworth high-pass — handy for dropping glider flow noise."""
    wn = min(cutoff_hz, _nyquist(df) * 0.99) / _nyquist(df)
    return _sos_filter(df, signal.butter(order, wn, btype="highpass", output="sos"))


def bandpass(
    df: pd.DataFrame, low_hz: float = 100.0, high_hz: float = 5000.0, order: int = 4
) -> pd.DataFrame:
    """Zero-phase Butterworth band-pass between *low_hz* and *high_hz*."""
    nyq = _nyquist(df)
    low = max(low_hz, 1e-6) / nyq
    high = min(high_hz, nyq * 0.99) / nyq
    if low >= high:
        raise ValueError(f"low_hz ({low_hz}) must be below high_hz ({high_hz})")
    return _sos_filter(df, signal.butter(order, [low, high], btype="bandpass", output="sos"))


def notch(df: pd.DataFrame, freq_hz: float = 60.0, q: float = 30.0) -> pd.DataFrame:
    """Narrow IIR notch, e.g. to suppress a tonal self-noise line."""
    b, a = signal.iirnotch(min(freq_hz, _nyquist(df) * 0.99), q, fs=df.attrs["sample_rate"])
    out = df.copy()
    for col in channel_columns(df):
        out[col] = signal.filtfilt(b, a, df[col].to_numpy(dtype=np.float64))
    return carry_attrs(out, df)


def moving_average(df: pd.DataFrame, window_ms: float = 1.0) -> pd.DataFrame:
    """Centered boxcar smoother; window given in milliseconds.

    Zero-phase: the window is forced to an odd length so it sits symmetrically
    on the sample it labels.
    """
    n = _odd(round(window_ms * 1e-3 * df.attrs["sample_rate"]))
    out = df.copy()
    for col in channel_columns(df):
        out[col] = df[col].rolling(n, center=True, min_periods=1).mean()
    return carry_attrs(out, df)


def normalize(df: pd.DataFrame, mode: str = "peak") -> pd.DataFrame:
    """Rescale each channel by its peak, RMS, or z-score."""
    out = df.copy()
    for col in channel_columns(df):
        x = df[col].to_numpy(dtype=np.float64)
        if mode == "peak":
            denom = np.max(np.abs(x))
        elif mode == "rms":
            denom = np.sqrt(np.mean(x**2))
        elif mode == "zscore":
            x = x - x.mean()
            denom = x.std()
        else:
            raise ValueError(f"unknown mode: {mode}")
        out[col] = x / denom if denom else x
    return carry_attrs(out, df, y_label=f"Amplitude ({mode}-normalized)")


def envelope(df: pd.DataFrame, smooth_ms: float = 5.0) -> pd.DataFrame:
    """Analytic (Hilbert) amplitude envelope, optionally smoothed.

    Zero-phase: the Hilbert magnitude is phase-free and the smoothing window is
    forced to an odd length so it stays centered.
    """
    out = df.copy()
    n = _odd(round(smooth_ms * 1e-3 * df.attrs["sample_rate"]))
    for col in channel_columns(df):
        env = np.abs(signal.hilbert(df[col].to_numpy(dtype=np.float64)))
        out[col] = pd.Series(env).rolling(n, center=True, min_periods=1).mean().to_numpy()
    return carry_attrs(out, df, y_label="Envelope amplitude")


def downsample(df: pd.DataFrame, factor: int = 4) -> pd.DataFrame:
    """Anti-aliased decimation by an integer *factor* (sample rate drops too)."""
    factor = max(1, int(factor))
    if factor == 1:
        return passthrough(df)
    xcol = x_column(df)
    cols = channel_columns(df)
    data = {xcol: df[xcol].to_numpy()[::factor]}
    for col in cols:
        data[col] = signal.decimate(
            df[col].to_numpy(dtype=np.float64), factor, ftype="fir", zero_phase=True
        )
    n = min(len(v) for v in data.values())
    out = pd.DataFrame({k: v[:n] for k, v in data.items()})
    return carry_attrs(out, df, sample_rate=int(df.attrs["sample_rate"] / factor))


# --------------------------------------------------------------------------
# transforms — time domain in, frequency domain out
# --------------------------------------------------------------------------
def fft(
    df: pd.DataFrame,
    window: str = "hann",
    scale: str = "dB",
    fmax_hz: float = 0.0,
    detrend: bool = True,
) -> pd.DataFrame:
    """One-sided magnitude spectrum of each channel.

    ``fmax_hz=0`` keeps the full band up to Nyquist.  This is the canonical
    example of a transform that changes domain: the returned frame's axis is
    ``freq_hz`` and ``attrs["domain"]`` becomes ``"frequency"``.
    """
    sr = df.attrs["sample_rate"]
    n = len(df)
    win = signal.get_window(window, n) if window != "none" else np.ones(n)
    correction = win.sum() or 1.0

    freqs = np.fft.rfftfreq(n, d=1.0 / sr)
    out = pd.DataFrame({"freq_hz": freqs})
    for col in channel_columns(df):
        x = df[col].to_numpy(dtype=np.float64)
        if detrend:
            x = signal.detrend(x, type="constant")
        mag = np.abs(np.fft.rfft(x * win)) * 2.0 / correction
        out[col] = 20 * np.log10(mag + 1e-12) if scale == "dB" else mag

    if fmax_hz and fmax_hz > 0:
        out = out[out["freq_hz"] <= fmax_hz].reset_index(drop=True)

    return carry_attrs(
        out,
        df,
        x="freq_hz",
        x_label="Frequency (Hz)",
        y_label="Magnitude (dB)" if scale == "dB" else "Magnitude",
        domain="frequency",
    )


def psd_welch(
    df: pd.DataFrame,
    nperseg: int = 4096,
    overlap_pct: float = 50.0,
    scale: str = "dB",
) -> pd.DataFrame:
    """Welch power spectral density — the averaged, lower-variance cousin of fft."""
    sr = df.attrs["sample_rate"]
    nperseg = int(min(nperseg, len(df)))
    noverlap = int(nperseg * overlap_pct / 100.0)

    out = None
    for col in channel_columns(df):
        f, pxx = signal.welch(
            df[col].to_numpy(dtype=np.float64), fs=sr, nperseg=nperseg, noverlap=noverlap
        )
        if out is None:
            out = pd.DataFrame({"freq_hz": f})
        out[col] = 10 * np.log10(pxx + 1e-20) if scale == "dB" else pxx

    return carry_attrs(
        out,
        df,
        x="freq_hz",
        x_label="Frequency (Hz)",
        y_label="PSD (dB re 1/Hz)" if scale == "dB" else "PSD (1/Hz)",
        domain="frequency",
    )


# --------------------------------------------------------------------------
# registry — this dict populates the dropdown in app.py
# --------------------------------------------------------------------------
TRANSFORMS: dict[str, Transform] = {
    "Passthrough": Transform(
        func=passthrough,
        description="No change; the residual should be flat zero.",
    ),
    "Low-pass": Transform(
        func=lowpass,
        description="Butterworth low-pass filter.",
        params=[
            Param("cutoff_hz", "Cutoff (Hz)", "float", 1000.0, 1.0, 96000.0, 10.0,
                  max_from="nyquist"),
            Param("order", "Order", "int", 4, 1, 10, 1),
        ],
    ),
    "High-pass": Transform(
        func=highpass,
        description="Butterworth high-pass; useful against low-frequency flow noise.",
        params=[
            Param("cutoff_hz", "Cutoff (Hz)", "float", 100.0, 1.0, 96000.0, 10.0,
                  max_from="nyquist"),
            Param("order", "Order", "int", 4, 1, 10, 1),
        ],
    ),
    "Band-pass": Transform(
        func=bandpass,
        description="Keep energy between two frequencies.",
        params=[
            Param("low_hz", "Low cut (Hz)", "float", 100.0, 1.0, 96000.0, 10.0,
                  max_from="nyquist"),
            Param("high_hz", "High cut (Hz)", "float", 5000.0, 2.0, 96000.0, 10.0,
                  max_from="nyquist"),
            Param("order", "Order", "int", 4, 1, 10, 1),
        ],
    ),
    "Notch": Transform(
        func=notch,
        description="Suppress a single tonal line.",
        params=[
            Param("freq_hz", "Notch (Hz)", "float", 60.0, 1.0, 96000.0, 1.0,
                  max_from="nyquist"),
            Param("q", "Q", "float", 30.0, 1.0, 100.0, 1.0),
        ],
    ),
    "Moving average": Transform(
        func=moving_average,
        description="Boxcar smoothing in the time domain.",
        params=[Param("window_ms", "Window (ms)", "float", 1.0, 0.01, 100.0, 0.01)],
    ),
    "Normalize": Transform(
        func=normalize,
        description="Rescale each channel.",
        params=[Param("mode", "Mode", "choice", "peak", options=("peak", "rms", "zscore"))],
    ),
    "Envelope": Transform(
        func=envelope,
        description="Hilbert amplitude envelope.",
        params=[Param("smooth_ms", "Smoothing (ms)", "float", 5.0, 0.0, 200.0, 0.5)],
    ),
    "Downsample": Transform(
        func=downsample,
        description="Anti-aliased integer decimation.",
        params=[Param("factor", "Factor", "int", 4, 1, 64, 1)],
    ),
    "FFT": Transform(
        func=fft,
        description="One-sided magnitude spectrum.",
        domain="frequency",
        params=[
            Param("window", "Window", "choice", "hann",
                  options=("hann", "hamming", "blackman", "boxcar", "none")),
            Param("scale", "Scale", "choice", "dB", options=("dB", "linear")),
            Param("fmax_hz", "Max frequency (Hz, 0 = all)", "float", 0.0, 0.0, 96000.0,
                  100.0, max_from="nyquist"),
            Param("detrend", "Remove DC", "bool", True),
        ],
    ),
    "PSD (Welch)": Transform(
        func=psd_welch,
        description="Averaged power spectral density.",
        domain="frequency",
        params=[
            Param("nperseg", "Segment length", "int", 4096, 256, 65536, 256),
            Param("overlap_pct", "Overlap (%)", "float", 50.0, 0.0, 90.0, 5.0),
            Param("scale", "Scale", "choice", "dB", options=("dB", "linear")),
        ],
    ),
}


def list_transforms() -> list[str]:
    """Names for the app's dropdown, in registry order."""
    return list(TRANSFORMS)


def get_transform(name: str) -> Transform:
    return TRANSFORMS[name]


def apply_transform(df: pd.DataFrame, name: str, **params) -> pd.DataFrame:
    """Look up *name* and run it — the single call ``app.py`` makes."""
    return get_transform(name).func(df, **params)


# --------------------------------------------------------------------------
# display-side DSP: used by plots.py to build the Y-axis views, not registered
# as selectable transforms because their output is 2-D rather than tabular
# --------------------------------------------------------------------------
def compute_spectrogram(
    df: pd.DataFrame,
    channel: str,
    nperseg: int = 1024,
    overlap_pct: float = 50.0,
    scale: str = "dB",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Short-time power spectrogram of one channel.

    Returns ``(freqs, times, Z)`` where ``Z`` has shape ``(len(freqs), len(times))``.
    Times are absolute — offset by the frame's own start time — so a spectrogram
    shares an x-axis with the waveform it came from.
    """
    if df.attrs.get("domain") != "time":
        raise ValueError("spectrogram requires a time-domain frame")

    sr = df.attrs["sample_rate"]
    x = df[channel].to_numpy(dtype=np.float64)
    nperseg = int(max(16, min(nperseg, len(x))))
    noverlap = int(np.clip(nperseg * overlap_pct / 100.0, 0, nperseg - 1))

    f, t, sxx = signal.spectrogram(
        x, fs=sr, nperseg=nperseg, noverlap=noverlap, scaling="density", mode="psd"
    )
    z = 10 * np.log10(sxx + 1e-20) if scale == "dB" else sxx
    return f, t + float(df[x_column(df)].iloc[0]), z
