"""Loading of glider .wav/.flac recordings into tidy DataFrames.

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
    df.attrs["start_s"]     offset of the loaded window into the recording
    df.attrs["duration_s"]  length of the loaded window, in seconds
    df.attrs["n_samples"]   frames per channel that were read

``start_s``/``duration_s``/``n_samples`` describe the *window that was read*,
so a transform that drops the time axis (an FFT, say) still carries how much
signal it was computed from -- see :func:`window_span`.

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
FLAC_EXTENSIONS = (".flac", ".FLAC")
AUDIO_EXTENSIONS = WAV_EXTENSIONS + FLAC_EXTENSIONS


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


def window_span(df: pd.DataFrame) -> dict:
    """How much signal this frame holds: start, end, duration, samples, rate.

    A time-domain frame carries its own time axis, so the span is measured from
    it -- and runs one sample period past the last timestamp, because the final
    sample covers a sample period too.  A frequency-domain frame has no time
    axis left, so it falls back to the window ``load_data`` recorded in
    ``attrs``.  Either way the answer is the length of the signal in memory,
    which is what the plots label themselves with.
    """
    sr = float(df.attrs.get("sample_rate", 0.0) or 0.0)
    n = len(df)

    if df.attrs.get("domain") == "time" and n:
        x = df[x_column(df)].to_numpy(dtype=np.float64)
        if sr:
            step = 1.0 / sr
        else:  # no rate recorded: infer one from the axis itself
            step = float(x[-1] - x[0]) / (n - 1) if n > 1 else 0.0
        start, end, n_samples = float(x[0]), float(x[-1]) + step, n
    else:
        start = float(df.attrs.get("start_s", 0.0))
        end = start + float(df.attrs.get("duration_s", 0.0))
        n_samples = int(df.attrs.get("n_samples", 0))

    return {
        "start_s": start,
        "end_s": end,
        "duration_s": end - start,
        "n_samples": n_samples,
        "sample_rate": sr,
    }


# --------------------------------------------------------------------------
# file discovery + raw reading
# --------------------------------------------------------------------------
def _list_by_extension(directory: str, extensions: tuple[str, ...]) -> list[str]:
    """Sorted paths in *directory* (non-recursive) ending in *extensions*."""
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return sorted(os.path.join(directory, n) for n in names if n.endswith(extensions))


def list_wav_files(directory: str = ".") -> list[str]:
    """Sorted list of .wav paths in *directory* (non-recursive)."""
    return _list_by_extension(directory, WAV_EXTENSIONS)


def list_flac_files(directory: str = ".") -> list[str]:
    """Sorted list of .flac paths in *directory* (non-recursive)."""
    return _list_by_extension(directory, FLAC_EXTENSIONS)


def list_audio_files(directory: str = ".") -> list[str]:
    """Sorted list of every readable audio path in *directory* (.wav + .flac)."""
    return _list_by_extension(directory, AUDIO_EXTENSIONS)


def is_flac(source) -> bool:
    """True if *source* names a .flac file (path, or upload with a ``.name``)."""
    name = getattr(source, "name", source)
    if not isinstance(name, (str, os.PathLike)):
        return False
    return os.fspath(name).endswith(FLAC_EXTENSIONS)


def _require_soundfile(fmt: str) -> None:
    if sf is None:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            f"reading {fmt} needs the 'soundfile' package (pip install soundfile); "
            "the stdlib 'wave' fallback only understands .wav"
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


def flac_info(source) -> dict:
    """Header-only probe of a .flac file; same keys as :func:`wav_info`.

    Requires ``soundfile`` -- the stdlib ``wave`` fallback cannot read FLAC.
    """
    _require_soundfile("FLAC")
    info = sf.info(source)
    return {
        "sample_rate": int(info.samplerate),
        "n_channels": int(info.channels),
        "n_frames": int(info.frames),
        "duration_s": float(info.frames) / info.samplerate,
        "subtype": info.subtype,
    }


def audio_info(source) -> dict:
    """Probe a .wav or .flac file, dispatching on the file name."""
    return flac_info(source) if is_flac(source) else wav_info(source)


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


def read_flac(source, start_s: float = 0.0, duration_s: float | None = None):
    """Read a slice of a flac file, exactly as :func:`read_wav` does for wav.

    Parameters
    ----------
    source : path or file-like (e.g. a Streamlit upload)
    start_s : offset into the recording, in seconds
    duration_s : length to read; ``None`` reads to the end of the file

    Returns
    -------
    (samples, sample_rate) where samples has shape (frames, channels), float32.
    """
    _require_soundfile("FLAC")
    with sf.SoundFile(source) as f:
        sr = int(f.samplerate)
        start = max(0, int(round(start_s * sr)))
        frames = -1 if duration_s is None else int(round(duration_s * sr))
        f.seek(min(start, len(f)))
        data = f.read(frames=frames, dtype="float32", always_2d=True)
    return data, sr


def read_audio(source, start_s: float = 0.0, duration_s: float | None = None):
    """Read a slice of a .wav or .flac file, dispatching on the file name."""
    reader = read_flac if is_flac(source) else read_wav
    return reader(source, start_s, duration_s)


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
        duration_s=float(samples.shape[0]) / float(sample_rate),
        n_samples=int(samples.shape[0]),
    )
    return df


# --------------------------------------------------------------------------
# the entry point app.py calls
# --------------------------------------------------------------------------
# CSS for the Input block only.  Streamlit's own ``gap`` handles the space
# *between* widgets; these rules tighten what is left inside each one, so the
# whole section fits above the fold and the chain below it stays in view.
_INPUT_CSS = """
<style>
.st-key-input-panel [data-testid="stWidgetLabel"] p { margin-bottom: .1rem; }
.st-key-input-panel [data-testid="stCaptionContainer"] p { margin: .1rem 0; }
.st-key-input-panel [data-testid="stSliderTickBar"] { font-size: .65rem; }
.st-key-input-panel [data-baseweb="select"] > div { min-height: 2.1rem; }
</style>
"""


def load_data(directory: str = ".") -> pd.DataFrame:
    """Render the sidebar file/window controls and return the selected slice.

    This is the function ``app.py`` calls as ``df = load_data()``.  It keeps all
    of the I/O-shaped Streamlit widgets in one place so the main app stays
    focused on transforming and plotting.  Everything it draws lives in one
    compact container: the Input block is the part of the sidebar you set once
    and then leave alone, so it gives up its whitespace to the chain below it.
    """
    import streamlit as st  # imported lazily so data.py stays usable headless

    st.sidebar.header("Input")
    st.sidebar.markdown(_INPUT_CSS, unsafe_allow_html=True)
    panel = st.sidebar.container(key="input-panel", gap="xxsmall")

    found = list_audio_files(directory)
    labels = [os.path.basename(p) for p in found]
    choice = panel.selectbox(
        "File", labels + ["Upload…"], index=0 if labels else len(labels)
    )

    if choice == "Upload…":
        upload = panel.file_uploader("Choose a .wav or .flac", type=["wav", "flac"])
        if upload is None:
            st.info("Select or upload a .wav or .flac file to begin.")
            st.stop()
        source, name = upload, upload.name
    else:
        source, name = found[labels.index(choice)], choice

    try:
        info = audio_info(source)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user
        st.error(f"Could not read {name}: {exc}")
        st.stop()

    panel.caption(
        f"{info['sample_rate']:,} Hz · {info['n_channels']} ch · "
        f"{info['duration_s']:.1f} s · {info['subtype']}"
    )

    max_start = max(0.0, info["duration_s"] - 0.01)
    start_s = panel.slider("Start (s)", 0.0, float(max_start), 0.0, step=0.1)
    duration_s = panel.slider(
        "Window (s)",
        0.1,
        float(min(60.0, info["duration_s"])),
        float(min(5.0, info["duration_s"])),
        step=0.1,
        help="Length of signal loaded into memory and fed to the chain.",
    )
    # The sliders only say where the window starts and how long it is; this
    # says what that actually selects, so a nudge of either has a visible answer.
    window_end = min(start_s + duration_s, info["duration_s"])
    panel.caption(
        f"Loading **{window_end - start_s:.2f} s** · "
        f"{start_s:.2f}–{window_end:.2f} s of {info['duration_s']:.1f} s · "
        f"{int(round((window_end - start_s) * info['sample_rate'])):,} samples/ch"
    )

    all_channels = list(range(info["n_channels"]))
    picked = panel.multiselect(
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
    """Cache reads keyed by (file, window) so slider tweaks stay responsive."""
    import streamlit as st

    # Only the source is underscored, and it has to be: Streamlit leaves
    # underscore-prefixed arguments *out* of the cache key, so anything the
    # window depends on must keep a plain name or every slider position would
    # be served the first read.  The source itself cannot be hashed (an upload
    # is a file object), so ``key`` below stands in for its identity.
    @st.cache_data(show_spinner="Reading audio…")
    def _read(_source, key: str, start_s: float, duration_s: float):
        return read_audio(_source, start_s, duration_s)

    return _read(source, _source_key(source, name), start_s, duration_s)


def _source_key(source, name: str) -> str:
    """Stable identity for a cache key: path + mtime, or upload name + size."""
    if isinstance(source, str):
        try:
            return f"{source}|{os.path.getmtime(source)}"
        except OSError:
            return source
    return f"upload:{name}|{getattr(source, 'size', '')}"
