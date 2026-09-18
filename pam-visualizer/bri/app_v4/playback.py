"""Listening to the loaded window.

The audio is played straight from the frame already in memory, so nothing is
re-read from disk and whatever the chain did to the signal is what you hear.

Two things make glider audio awkward to play in a browser:

*Rate.*  These recorders run at 200 kHz.  No browser will play that, so the
signal is resampled down to something it will accept.  Played at real speed
that means you only ever hear the audible band — everything above ~24 kHz,
which is most of what a 200 kHz recorder was deployed to catch, is gone.

*Pitch.*  The fix bioacousticians use is time expansion: play the samples out
more slowly than they came in.  Slowing by ten brings a 60 kHz click down to
6 kHz where you can hear it, at the cost of the clip taking ten times as long.
That is what the Speed control does.
"""

from __future__ import annotations

import io
import wave

import numpy as np
import pandas as pd
import streamlit as st
from scipy import signal

from data import channel_columns

# Browsers reliably play up to 48 kHz; above that support gets patchy.
MAX_PLAYBACK_RATE = 48_000

# Expansion factor -> label. 1 is real speed, audible band only.
SPEED_CHOICES = [
    ("Real speed", 1),
    ("½ speed", 2),
    ("¼ speed", 4),
    ("⅒ speed", 10),
    ("1/20 speed", 20),
]

# Warn beyond this many seconds of resulting audio.
LONG_CLIP_S = 180.0


def _to_playable(x: np.ndarray, sample_rate: int, expansion: int):
    """Return (samples, output_rate) a browser will actually play.

    Time expansion is free: declaring a lower rate for the same samples is
    exactly what slowing the playback means. Only when the declared rate is
    still too high does anything need resampling.
    """
    out_rate = sample_rate / float(expansion)

    if out_rate > MAX_PLAYBACK_RATE:
        # Decimate to the ceiling. Duration and pitch are unchanged; the band
        # above half the new rate is filtered away rather than aliased down.
        up, down = MAX_PLAYBACK_RATE, int(round(out_rate))
        divisor = np.gcd(up, down)
        x = signal.resample_poly(x, up // divisor, down // divisor)
        out_rate = MAX_PLAYBACK_RATE

    return x, int(round(out_rate))


def _normalize(x: np.ndarray, headroom_db: float = 1.0) -> np.ndarray:
    """Peak-normalize with a little headroom, leaving silence alone."""
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= 0:
        return x
    target = 10.0 ** (-headroom_db / 20.0)
    return x * (target / peak)


def encode_wav(x: np.ndarray, sample_rate: int) -> bytes:
    """16-bit PCM WAV bytes for *x*, which must already sit in [-1, 1].

    Handing Streamlit a numpy array would work, but it re-scales the array by
    its own peak before encoding, which silently overrides any level choice
    made here — including turning a deliberately quiet clip up to full volume.
    Encoding here keeps the level under our control and makes the exact bytes
    available to download.
    """
    x = np.nan_to_num(np.asarray(x, dtype=np.float64), nan=0.0,
                      posinf=0.0, neginf=0.0)
    clipped = np.clip(x, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(int(sample_rate))
        out.setcomptype("NONE", "NONE")
        out.writeframes(pcm.tobytes())
    return buffer.getvalue()


def render_playback(df: pd.DataFrame, label: str = "Listen") -> None:
    """Audio player for the window held in *df*.

    Silently does nothing for a frequency-domain frame: a spectrum has no
    samples to play.
    """
    if df.attrs.get("domain") != "time":
        return

    channels = channel_columns(df)
    sample_rate = int(df.attrs.get("sample_rate", 0))
    if not channels or sample_rate <= 0:
        return

    st.subheader(label)

    controls = st.columns([1, 1, 1, 1, 2])

    channel = (
        controls[0].selectbox("Channel", channels, key="play_channel")
        if len(channels) > 1
        else channels[0]
    )
    if len(channels) == 1:
        controls[0].caption(f"Channel {channels[0]}")

    speed_label = controls[1].selectbox(
        "Speed", [c[0] for c in SPEED_CHOICES], index=0, key="play_speed",
        help="Real speed plays only the audible band, because the file is "
             "sampled far above hearing. Slower speeds shift ultrasonic "
             "content down into the range you can hear, and take "
             "proportionally longer to play.",
    )
    expansion = dict(SPEED_CHOICES)[speed_label]

    remove_dc = controls[2].checkbox(
        "Remove DC", value=True, key="play_remove_dc",
        help="Subtract the mean before playing. These recorders sit on a "
             "large DC offset, and normalizing without removing it first "
             "scales the offset instead of the sound, leaving the clip "
             "inaudible.",
    )

    normalize = controls[3].checkbox(
        "Normalize", value=True, key="play_normalize",
        help="Scale to near full volume. Glider recordings are often quiet "
             "enough to be inaudible otherwise.",
    )

    x = df[channel].to_numpy(dtype=np.float32)

    # Measured before anything is done to it, so the caption can report it.
    dc_offset = float(np.mean(x)) if x.size else 0.0
    ac_rms = float(np.sqrt(np.mean((x - dc_offset) ** 2))) if x.size else 0.0

    if remove_dc:
        x = x - dc_offset
    if normalize:
        x = _normalize(x)

    try:
        samples, out_rate = _to_playable(x, sample_rate, expansion)
    except Exception as exc:  # noqa: BLE001 - shown instead of the player
        st.warning(f"Could not prepare audio for playback: {exc}")
        return

    duration = len(samples) / out_rate
    if duration > LONG_CLIP_S:
        st.warning(
            f"This will play for {duration / 60:.1f} minutes at {speed_label}. "
            "Shorten the window, or pick a faster speed."
        )

    audio_bytes = encode_wav(samples, out_rate)
    st.audio(audio_bytes, format="audio/wav")

    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    peak_db = 20 * np.log10(peak) if peak > 0 else float("-inf")
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))) if samples.size else 0.0

    heard_to = min(sample_rate / 2.0, out_rate / 2.0 * expansion)
    stem = str(df.attrs.get("source", "audio")).rsplit(".", 1)[0]

    controls[4].download_button(
        "Download this clip",
        data=audio_bytes,
        file_name=f"{stem}_{channel}_{expansion}x.wav",
        mime="audio/wav",
        width="stretch",
        help="If the player above stays silent, download and open the file "
             "locally — that separates a bad clip from a browser or proxy "
             "that will not serve it.",
    )

    st.caption(
        f"{df.attrs.get('source', 'audio')} · {channel} · {duration:.1f} s at "
        f"{out_rate:,} Hz"
        + (
            f" · recorded band up to {heard_to / 1000:.0f} kHz is audible"
            if expansion > 1
            else f" · only the band below {out_rate / 2000:.0f} kHz is audible "
                 f"at real speed"
        )
        + ". You are hearing the chain's input window, not its output."
    )

    # A DC offset well above the signal is the usual reason a clip plays as
    # silence: normalizing scales the offset, not the sound.
    if ac_rms > 0 and abs(dc_offset) > 4 * ac_rms:
        margin = 20 * np.log10(abs(dc_offset) / ac_rms)
        if remove_dc:
            st.caption(
                f"This recording carries a DC offset of {dc_offset:+.4f} "
                f"({dc_offset * 32768:+.0f} counts), {margin:.0f} dB above the "
                "sound itself. It has been removed — leaving it in makes the "
                "clip play as silence."
            )
        else:
            st.warning(
                f"DC offset of {dc_offset:+.4f} ({dc_offset * 32768:+.0f} "
                f"counts) is {margin:.0f} dB above the actual signal. With "
                "Remove DC off, normalizing scales that offset rather than the "
                "sound, so this will play as silence. Tick **Remove DC**."
            )

    if peak <= 0:
        st.warning(
            "This window is digital silence — every sample is zero, so there "
            "is nothing to hear. Move the Start slider, or check the channel."
        )
    else:
        st.caption(
            f"Level sent to the player: peak {peak_db:.1f} dBFS, RMS "
            f"{20 * np.log10(rms):.1f} dBFS, {len(audio_bytes) / 1e6:.1f} MB. "
            + ("Turn Normalize on if this is too quiet to hear."
               if not normalize and peak_db < -30 else "")
        )
