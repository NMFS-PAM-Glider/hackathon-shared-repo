"""Listening to the loaded window, before and after the transform chain.

Two players are drawn side by side: the file as it was read, and the output of
the last step that ran. They share one set of controls, so the only difference
you hear between them is what the chain did — which is the point of having
both. A filter you cannot hear the effect of is worth a second look.

Three things make glider audio awkward to play in a browser:

*Rate.*  These recorders run at 200-240 kHz. No browser will play that, so the
signal is resampled down to something it will accept. Played at real speed
that means you only ever hear the audible band — everything above ~24 kHz,
which is most of what such a recorder was deployed to catch, is gone.

*Pitch.*  The fix bioacousticians use is time expansion: play the samples out
more slowly than they came in. Slowing by ten brings a 60 kHz click down to
6 kHz where you can hear it, at the cost of the clip taking ten times as long.
That is what the Speed control does.

*Offset.*  These recordings sit on a large DC offset — often tens of dB above
the sound itself. Normalizing without removing it first scales the offset
rather than the signal, and the clip plays as silence.
"""

from __future__ import annotations

import io
import wave

import numpy as np
import pandas as pd
import streamlit as st
from scipy import signal

from chain import final_result
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


# --------------------------------------------------------------------------
# signal preparation
# --------------------------------------------------------------------------
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
    Encoding here keeps the level under our control, which is what makes the
    two players comparable, and makes the exact bytes available to download.
    """
    x = np.nan_to_num(np.asarray(x, dtype=np.float64), nan=0.0,
                      posinf=0.0, neginf=0.0)
    pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(int(sample_rate))
        out.setcomptype("NONE", "NONE")
        out.writeframes(pcm.tobytes())
    return buffer.getvalue()


def prepare(frame, channel: str, expansion: int,
            remove_dc: bool, normalize: bool) -> dict | None:
    """Turn one frame's channel into playable bytes, with its measurements.

    Returns None when the frame holds nothing playable: a spectrum, no
    channels, or no sample rate.
    """
    if frame is None or frame.attrs.get("domain") != "time":
        return None

    if channel not in frame.columns:
        # A transform can rename or drop columns; fall back rather than fail.
        others = channel_columns(frame)
        if not others:
            return None
        channel = others[0]

    sample_rate = int(frame.attrs.get("sample_rate", 0))
    if sample_rate <= 0:
        return None

    x = frame[channel].to_numpy(dtype=np.float32)

    # Measured before anything is done, so the caption can report it.
    dc_offset = float(np.mean(x)) if x.size else 0.0
    ac_rms = float(np.sqrt(np.mean((x - dc_offset) ** 2))) if x.size else 0.0

    if remove_dc:
        x = x - dc_offset
    if normalize:
        x = _normalize(x)

    samples, out_rate = _to_playable(x, sample_rate, expansion)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = (float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
           if samples.size else 0.0)

    return {
        "channel": channel,
        "bytes": encode_wav(samples, out_rate),
        "rate": out_rate,
        "sample_rate": sample_rate,
        "duration": len(samples) / out_rate if out_rate else 0.0,
        "peak": peak,
        "peak_db": 20 * np.log10(peak) if peak > 0 else float("-inf"),
        "rms_db": 20 * np.log10(rms) if rms > 0 else float("-inf"),
        "dc_offset": dc_offset,
        "ac_rms": ac_rms,
    }


# --------------------------------------------------------------------------
# one player
# --------------------------------------------------------------------------
def _render_one(box, heading: str, subtitle: str, clip: dict | None,
                expansion: int, remove_dc: bool, stem: str, tag: str,
                unavailable: str = "") -> None:
    """Heading, player, download and level readout, inside *box*."""
    box.markdown(f"**{heading}**")
    box.caption(subtitle)

    if clip is None:
        box.info(unavailable or "Nothing to play here.")
        return

    box.audio(clip["bytes"], format="audio/wav")

    heard_to = min(clip["sample_rate"] / 2.0, clip["rate"] / 2.0 * expansion)
    box.caption(
        f"{clip['channel']} · {clip['duration']:.1f} s at {clip['rate']:,} Hz"
        + (f" · recorded band up to {heard_to / 1000:.0f} kHz audible"
           if expansion > 1
           else f" · only below {clip['rate'] / 2000:.0f} kHz audible")
    )

    box.download_button(
        "Download", data=clip["bytes"],
        file_name=f"{stem}_{tag}_{clip['channel']}_{expansion}x.wav",
        mime="audio/wav", width="stretch", key=f"play_dl_{tag}",
        help="If the player stays silent, download and open the file locally — "
             "that separates a bad clip from a browser or proxy that will not "
             "serve it.",
    )

    if clip["peak"] <= 0:
        box.warning("Digital silence — every sample is zero, nothing to hear.")
    else:
        box.caption(
            f"peak {clip['peak_db']:.1f} dBFS · RMS {clip['rms_db']:.1f} dBFS "
            f"· {len(clip['bytes']) / 1e6:.1f} MB"
        )

    # A DC offset well above the signal is the usual reason a clip plays as
    # silence: normalizing scales the offset, not the sound.
    if clip["ac_rms"] > 0 and abs(clip["dc_offset"]) > 4 * clip["ac_rms"]:
        margin = 20 * np.log10(abs(clip["dc_offset"]) / clip["ac_rms"])
        counts = clip["dc_offset"] * 32768
        if remove_dc:
            box.caption(
                f"DC offset of {clip['dc_offset']:+.4f} ({counts:+.0f} counts) "
                f"was {margin:.0f} dB above the sound, and has been removed."
            )
        else:
            box.warning(
                f"DC offset of {clip['dc_offset']:+.4f} ({counts:+.0f} counts) "
                f"is {margin:.0f} dB above the actual signal. With Remove DC "
                "off, normalizing scales the offset rather than the sound, so "
                "this plays as silence. Tick **Remove DC**."
            )


# --------------------------------------------------------------------------
# the entry point app.py calls
# --------------------------------------------------------------------------
def render_playback(df: pd.DataFrame, stages=None, label: str = "Listen") -> None:
    """Players for the loaded window and for the chain's final output.

    *stages* is the list returned by ``chain.chain_controls``. Passing None, or
    a chain that produced nothing playable, leaves the original on its own with
    a note saying why.
    """
    if df.attrs.get("domain") != "time":
        return

    channels = channel_columns(df)
    if not channels or int(df.attrs.get("sample_rate", 0)) <= 0:
        return

    st.subheader(label)

    # ---- shared controls -------------------------------------------------
    # One set for both players: the comparison only means anything if the two
    # clips are treated identically.
    controls = st.columns(4)

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
        "Normalize each", value=True, key="play_normalize",
        help="Scale each clip to near full volume. Easier to hear, but it "
             "hides how much level the chain removed — untick to compare the "
             "two at their true relative loudness.",
    )

    stages = list(stages or [])
    ran = [s for s in stages if getattr(s, "ok", False)]
    final = final_result(stages) if stages else None
    source = str(df.attrs.get("source", "audio"))
    stem = source.rsplit(".", 1)[0]

    try:
        original = prepare(df, channel, expansion, remove_dc, normalize)
        processed = prepare(final, channel, expansion, remove_dc, normalize)
    except Exception as exc:  # noqa: BLE001 - shown instead of the players
        st.warning(f"Could not prepare audio for playback: {exc}")
        return

    longest = max((c["duration"] for c in (original, processed) if c), default=0.0)
    if longest > LONG_CLIP_S:
        st.warning(
            f"These will play for {longest / 60:.1f} minutes at {speed_label}. "
            "Shorten the window, or pick a faster speed."
        )

    # ---- the two players -------------------------------------------------
    chain_names = " → ".join(s.name for s in ran)

    if final is None:
        subtitle = "nothing to play"
        unavailable = (
            "No step in the chain produced an output, so there is nothing to "
            "compare against."
        )
    elif final.attrs.get("domain") != "time":
        subtitle = chain_names or "chain output"
        unavailable = (
            f"The chain ends in **{ran[-1].name if ran else 'a spectrum'}**, "
            "which outputs a spectrum rather than a signal. A spectrum has no "
            "samples to play."
        )
    else:
        subtitle = chain_names or "chain output"
        unavailable = ""

    left, right = st.columns(2)
    _render_one(left, "Original", source, original,
                expansion, remove_dc, stem, "original")
    _render_one(right, "After chain", subtitle, processed,
                expansion, remove_dc, stem, "chain", unavailable)

    # ---- what the comparison is worth ------------------------------------
    if ran and all(s.name == "Passthrough" for s in ran):
        st.caption(
            "The chain is Passthrough only, so the two clips are identical. "
            "Pick a function in the sidebar to hear a difference."
        )
    elif original and processed:
        if normalize:
            st.caption(
                "Both clips are normalized, so they play at a similar volume "
                "even where the chain removed most of the energy. Untick "
                "**Normalize each** to hear the real change in level."
            )
        else:
            change = processed["rms_db"] - original["rms_db"]
            st.caption(
                f"The chain changed the level by {change:+.1f} dB RMS "
                f"({original['rms_db']:.1f} → {processed['rms_db']:.1f} dBFS). "
                "Both clips are at their true relative loudness."
                # Honest levels are often inaudible: these recordings sit tens
                # of dB below full scale once the DC offset is taken out.
                + (" Both are very quiet at true level — turn **Normalize "
                   "each** back on to hear them, at the cost of the comparison."
                   if max(original["peak_db"], processed["peak_db"]) < -40
                   else "")
            )

        if processed["sample_rate"] != original["sample_rate"]:
            st.caption(
                f"The chain also changed the sample rate: "
                f"{original['sample_rate']:,} → {processed['sample_rate']:,} Hz, "
                "so the two clips no longer carry the same bandwidth."
            )
