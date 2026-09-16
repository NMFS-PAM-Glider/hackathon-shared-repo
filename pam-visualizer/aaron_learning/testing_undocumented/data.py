"""Loading of glider .wav recordings into tidy DataFrames.

Conventions used across this package
------------------------------------
Every DataFrame produced here (and returned by ``transformers``) is "long in
columns": the first column is the independent axis and every remaining column
is one data channel.  Metadata travels in ``df.attrs``:

    df.attrs["x"]           name of the independent-axis column
    df.attrs["x_label"]     axis label for plots
    df.attrs["y_label"]     axis label for plots
    df.attrs["sample_rate"] samples per second of the *time-domain* signal
    df.attrs["domain"]      "time" or "frequency"
    df.attrs["source"]      name of the originating file

``pandas`` does not reliably propagate ``attrs`` through arithmetic, so use
:func:`carry_attrs` whenever you build a new frame from an old one.
"""

from __future__ import annotations

import os
import wave
from typing import Sequence

import numpy as np
import pandas as pd

try:  # optional, but much faster / handles more encodings
    import soundfile as sf
except ImportError:  # pragma: no cover - fallback path
    sf = None


WAV_EXTENSIONS = (".wav", ".WAV")


# --------------------------------------------------------------------------
# attrs helpers
# --------------------------------------------------------------------------
def carry_attrs(new: pd.DataFrame, old: pd.DataFrame, **overrides) -> pd.DataFrame:
    """Copy ``old.attrs`` onto ``new``, applying any keyword overrides."""
    new.attrs = {**old.attrs, **overrides}
    return new


def x_column(df: pd.DataFrame) -> str:
    """Name of the independent-axis column (falls back to the first column)."""
    return df.attrs.get("x", df.columns[0])


def channel_columns(df: pd.DataFrame) -> list[str]:
    """Every column except the independent axis."""
    return [c for c in df.columns if c != x_column(df)]


# --------------------------------------------------------------------------
# file discovery + raw reading
# --------------------------------------------------------------------------
def list_wav_files(directory: str = ".") -> list[str]:
    """Sorted list of .wav paths in *directory* (non-recursive)."""
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return sorted(
        os.path.join(directory, n) for n in names if n.endswith(WAV_EXTENSIONS)
    )


def wav_info(source) -> dict:
    """Header-only probe: sample rate, channel count, frame count, duration."""
    if sf is not None:
        info = sf.info(source)
        return {
            "sample_rate": int(info.samplerate),
            "n_channels": int(info.channels),
            "n_frames": int(info.frames),
            "duration_s": float(info.frames) / info.samplerate,
            "subtype": info.subtype,
        }
    with wave.open(source, "rb") as w:
        sr, n_frames = w.getframerate(), w.getnframes()
        return {
            "sample_rate": int(sr),
            "n_channels": int(w.getnchannels()),
            "n_frames": int(n_frames),
            "duration_s": n_frames / float(sr),
            "subtype": f"PCM_{w.getsampwidth() * 8}",
        }


def _pcm_to_float(raw: bytes, sampwidth: int, n_channels: int) -> np.ndarray:
    """Decode interleaved PCM bytes to float32 in [-1, 1], shape (frames, ch)."""
    if sampwidth == 1:  # 8-bit wav is unsigned
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        data = (data - 128.0) / 128.0
    elif sampwidth == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 2**15
    elif sampwidth == 3:  # 24-bit: sign-extend three little-endian bytes
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        ints = (b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)).astype(np.int32)
        ints = np.where(ints >= 2**23, ints - 2**24, ints)
        data = ints.astype(np.float32) / 2**23
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2**31
    else:
        raise ValueError(f"unsupported sample width: {sampwidth} bytes")
    return data.reshape(-1, n_channels)


def read_wav(source, start_s: float = 0.0, duration_s: float | None = None):
    """Read a slice of a wav file.

    Parameters
    ----------
    source : path or file-like (e.g. a Streamlit upload)
    start_s : offset into the recording, in seconds
    duration_s : length to read; ``None`` reads to the end of the file

    Returns
    -------
    (samples, sample_rate) where samples has shape (frames, channels), float32.
    """
    if sf is not None:
        with sf.SoundFile(source) as f:
            sr = int(f.samplerate)
            start = max(0, int(round(start_s * sr)))
            frames = -1 if duration_s is None else int(round(duration_s * sr))
            f.seek(min(start, len(f)))
            data = f.read(frames=frames, dtype="float32", always_2d=True)
        return data, sr

    if hasattr(source, "seek"):
        source.seek(0)
    with wave.open(source, "rb") as w:
        sr = w.getframerate()
        n_ch, width = w.getnchannels(), w.getsampwidth()
        start = max(0, min(int(round(start_s * sr)), w.getnframes()))
        w.setpos(start)
        n = w.getnframes() - start if duration_s is None else int(round(duration_s * sr))
        raw = w.readframes(max(0, n))
    return _pcm_to_float(raw, width, n_ch), int(sr)


def to_dataframe(
    samples: np.ndarray,
    sample_rate: int,
    start_s: float = 0.0,
    channels: Sequence[int] | None = None,
    source_name: str = "",
) -> pd.DataFrame:
    """Wrap raw samples in the package's standard time-domain DataFrame."""
    if samples.ndim == 1:
        samples = samples[:, None]
    picked = range(samples.shape[1]) if channels is None else list(channels)

    t = start_s + np.arange(samples.shape[0], dtype=np.float64) / sample_rate
    df = pd.DataFrame({"time_s": t})
    for ch in picked:
        df[f"ch{ch + 1}"] = samples[:, ch]

    df.attrs.update(
        x="time_s",
        x_label="Time (s)",
        y_label="Amplitude",
        sample_rate=int(sample_rate),
        domain="time",
        source=source_name,
        start_s=float(start_s),
    )
    return df


# --------------------------------------------------------------------------
# the entry point app.py calls
# --------------------------------------------------------------------------
def load_data(directory: str = ".") -> pd.DataFrame:
    """Render the sidebar file/window controls and return the selected slice.

    This is the function ``app.py`` calls as ``df = load_data()``.  It keeps all
    of the I/O-shaped Streamlit widgets in one place so the main app stays
    focused on transforming and plotting.
    """
    import streamlit as st  # imported lazily so data.py stays usable headless

    st.sidebar.header("Input")

    found = list_wav_files(directory)
    labels = [os.path.basename(p) for p in found]
    choice = st.sidebar.selectbox(
        "File", labels + ["Upload…"], index=0 if labels else len(labels)
    )

    if choice == "Upload…":
        upload = st.sidebar.file_uploader("Choose a .wav", type=["wav"])
        if upload is None:
            st.info("Select or upload a .wav file to begin.")
            st.stop()
        source, name = upload, upload.name
    else:
        source, name = found[labels.index(choice)], choice

    try:
        info = wav_info(source)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user
        st.error(f"Could not read {name}: {exc}")
        st.stop()

    st.sidebar.caption(
        f"{info['sample_rate']:,} Hz · {info['n_channels']} ch · "
        f"{info['duration_s']:.1f} s · {info['subtype']}"
    )

    max_start = max(0.0, info["duration_s"] - 0.01)
    start_s = st.sidebar.slider("Start (s)", 0.0, float(max_start), 0.0, step=0.1)
    duration_s = st.sidebar.slider(
        "Window (s)",
        0.1,
        float(min(60.0, info["duration_s"])),
        float(min(5.0, info["duration_s"])),
        step=0.1,
        help="Length of signal loaded into memory and fed to the transform.",
    )

    all_channels = list(range(info["n_channels"]))
    picked = st.sidebar.multiselect(
        "Channels",
        all_channels,
        default=all_channels[: min(2, len(all_channels))],
        format_func=lambda i: f"ch{i + 1}",
    )
    if not picked:
        st.warning("Select at least one channel.")
        st.stop()

    samples, sr = _cached_read(source, name, start_s, duration_s)
    return to_dataframe(samples, sr, start_s=start_s, channels=picked, source_name=name)


def _cached_read(source, name: str, start_s: float, duration_s: float):
    """Cache reads keyed by (name, window) so slider tweaks stay responsive."""
    import streamlit as st

    @st.cache_data(show_spinner="Reading audio…")
    def _read(_source, _name, _start, _dur):
        return read_wav(_source, _start, _dur)

    return _read(source, name, start_s, duration_s)
