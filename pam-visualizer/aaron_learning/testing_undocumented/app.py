"""Streamlit front end for inspecting ocean-glider hydrophone .wav files.

Run with:  streamlit run audio_vis/app.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import streamlit as st

from data import channel_columns, load_data
from plots import (
    MAX_POINTS,
    VIEWS,
    axis_revisions,
    link_figures,
    plot_difference,
    plot_original,
    plot_transformed,
    resolution_note,
    spectrogram_range,
)
from transformers import TRANSFORMS, get_transform, list_transforms

# DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = "/home/jovyan/shared-public/GliderRodeo/audio" #   When in JupyterHub

def transform_controls(name: str, nyquist: float) -> dict:
    """Build a sidebar widget per :class:`Param` and collect the chosen values."""
    params = {}
    for p in get_transform(name).params:
        key = f"{name}:{p.name}"
        upper = nyquist if p.max_from == "nyquist" else p.max

        if p.kind == "bool":
            params[p.name] = st.sidebar.checkbox(p.label, value=p.default, key=key,
                                                 help=p.help or None)
        elif p.kind == "choice":
            options = list(p.options)
            params[p.name] = st.sidebar.selectbox(
                p.label, options, index=options.index(p.default), key=key,
                help=p.help or None,
            )
        elif p.kind == "int":
            params[p.name] = int(st.sidebar.number_input(
                p.label, min_value=int(p.min), max_value=int(upper),
                value=int(min(p.default, upper)), step=int(p.step or 1), key=key,
                help=p.help or None,
            ))
        else:  # float
            params[p.name] = float(st.sidebar.number_input(
                p.label, min_value=float(p.min), max_value=float(upper),
                value=float(min(p.default, upper)), step=float(p.step or 1.0), key=key,
                help=p.help or None,
            ))
    return params


def view_controls(df, output_domain: str) -> tuple[str, dict, bool]:
    """Pick what goes on the Y axis, plus the options that view needs."""
    st.sidebar.header("Display")

    # A frequency-domain transform output is a spectrum already; the waveform
    # and spectrogram views have nothing to draw it on.
    available = ["Spectrum"] if output_domain == "frequency" else list(VIEWS)
    view = st.sidebar.selectbox(
        "View (Y axis)", available,
        help="Waveform: amplitude vs time. Spectrum: magnitude vs frequency. "
             "Spectrogram: frequency vs time, colored by level.",
    )
    if output_domain == "frequency":
        st.sidebar.caption("This transform already outputs a spectrum, so only the "
                           "Spectrum view applies; the residual is taken in "
                           "frequency against the input's own spectrum.")

    opts: dict = {}
    if view == "Spectrum":
        opts["window"] = st.sidebar.selectbox(
            "FFT window", ["hann", "hamming", "blackman", "boxcar", "none"]
        )
        opts["scale"] = st.sidebar.selectbox("Magnitude scale", ["dB", "linear"])
        opts["log_x"] = st.sidebar.checkbox("Log frequency axis", value=True)
    elif view == "Spectrogram":
        opts["channel"] = st.sidebar.selectbox(
            "Channel", channel_columns(df),
            help="A spectrogram shows one channel at a time.",
        )
        opts["nperseg"] = int(st.sidebar.select_slider(
            "FFT length", [256, 512, 1024, 2048, 4096, 8192], value=1024,
            help="Longer windows resolve frequency better, shorter ones time.",
        ))
        opts["overlap_pct"] = float(st.sidebar.slider("Overlap (%)", 0, 90, 50, step=5))
        opts["dynamic_range"] = float(
            st.sidebar.slider("Dynamic range (dB)", 20, 120, 60, step=5)
        )
        opts["colorscale"] = st.sidebar.selectbox(
            "Color scale", ["Viridis", "Inferno", "Magma", "Cividis", "Turbo", "Greys"]
        )
        opts["residual_autoscale"] = st.sidebar.checkbox(
            "Auto-scale residual colors", value=False,
            help="Off: the residual shares the input's color limits, so how much "
                 "energy the transform removed is read directly against the input. "
                 "On: the residual is stretched to its own range, which brings out "
                 "a quiet residual but makes it look as loud as the input.",
        )

    if view in ("Waveform", "Spectrum"):
        opts["max_points"] = int(st.sidebar.select_slider(
            "Points per trace",
            [1000, 2000, 4000, 8000, 16000, 32000, 64000], value=MAX_POINTS,
            help="How many points each line may use. Above this the trace is "
                 "drawn as a min/max envelope; at or below it every sample is "
                 "drawn and panels line up sample for sample.",
        ))
        span = float(df[df.attrs["x"]].iloc[-1] - df[df.attrs["x"]].iloc[0])
        st.sidebar.caption(resolution_note(len(df), span, opts["max_points"]))

    link_x = st.sidebar.checkbox(
        "Link X axes", value=True,
        help="Pan or zoom any panel and all three follow.",
    )
    return view, opts, link_x


def main() -> None:
    st.set_page_config(page_title="Glider Audio Viewer", layout="wide")
    st.title("Glider Audio Viewer")

    # 1. input ------------------------------------------------------------
    df = load_data(DATA_DIR)

    # 2. transform selection ----------------------------------------------
    st.sidebar.header("Transform")
    name = st.sidebar.selectbox("Function", list_transforms())
    st.sidebar.caption(TRANSFORMS[name].description)
    params = transform_controls(name, nyquist=df.attrs["sample_rate"] / 2.0)

    # 3. display selection -------------------------------------------------
    view, opts, link_x = view_controls(df, TRANSFORMS[name].domain)

    try:
        transformed = get_transform(name).func(df, **params)
        transformed.attrs["transform"] = name
        error = None
    except Exception as exc:  # noqa: BLE001 - shown in place of the figure
        transformed, error = None, exc

    if error is not None:
        st.error(f"{name} failed: {error}")
        st.stop()

    # 4. the three linked panels ------------------------------------------
    fig_in = plot_original(df, view, opts)
    # Reuse the input's color limits on the output so the two are comparable.
    shared_opts = {**opts, "zrange": spectrogram_range(fig_in)}
    fig_out = plot_transformed(transformed, view, shared_opts)
    # The residual shares them too unless asked otherwise: on its own limits an
    # all-zero residual stretches its floor across the whole color scale and
    # renders at full intensity, which reads as signal when it means silence.
    fig_res = plot_difference(
        df, transformed, view, opts if opts.get("residual_autoscale") else shared_opts
    )

    # Changing the transform must not throw away where you were looking, so the
    # zoom is tagged with what it depends on rather than with the transform.
    x_revision, y_revision = axis_revisions(
        df, view, opts, transform_key=f"{name}|{sorted(params.items())}"
    )

    st.plotly_chart(
        link_figures(
            [fig_in, fig_out, fig_res],
            link_x=link_x,
            # Frequency is the same quantity in every spectrogram panel, so the
            # Y axis is worth linking too; amplitude scales differ per panel.
            link_y=link_x and view == "Spectrogram",
            x_revision=x_revision,
            y_revision=y_revision,
        ),
        width="stretch",
        config={"scrollZoom": True},
        # A stable key keeps the chart mounted across reruns, which is what lets
        # Plotly apply the new data to the existing axes instead of redrawing.
        key="panels",
    )
    st.caption(
        ("Axes are linked — pan, zoom or box-select in any panel and the other two "
         "follow. " if link_x else "")
        + "Your zoom is kept when you change transform; it resets when you change "
          "file, window or view. Double-click to reset it yourself."
    )

    # 5. summary ----------------------------------------------------------
    st.subheader("Summary")
    st.caption(
        "Statistics of the **input** window, in full-scale units: samples are "
        "normalized so ±1.0 is the loudest value the recorder can represent."
    )
    cols = st.columns(len(channel_columns(df)) + 1)
    cols[0].metric(
        "Samples", f"{len(df):,}",
        help="Number of samples per channel in the loaded window "
             "(window length × sample rate).",
    )
    for col, ch in zip(cols[1:], channel_columns(df)):
        x = df[ch].to_numpy(dtype=np.float64)
        rms = float(np.sqrt(np.mean(x**2)))
        col.metric(
            f"{ch} RMS", f"{rms:.3e}", f"peak {np.abs(x).max():.3e}",
            delta_color="off",
            help="RMS is the root mean square of the samples — the square root "
                 "of their mean squared value. It tracks the average acoustic "
                 "energy over the whole window, so it is the number to watch "
                 "for sustained sound such as flow noise or vessel tonals. "
                 "Peak is the single largest absolute sample in the window: it "
                 "is set by the loudest instant, so it responds to transients "
                 "such as clicks that barely move the RMS, and it shows how "
                 "close the channel came to clipping at 1.0.",
        )
    st.caption(
        "**RMS** is the average level across the window — it answers *how loud "
        "was this stretch overall*, and is driven by sustained sound. **Peak** "
        "is the largest single sample — it answers *how loud did it ever get*, "
        "is driven by transients, and warns of clipping as it nears 1.0. A high "
        "peak beside a low RMS means brief, sharp events in otherwise quiet "
        "water; the two converging means continuous noise. Both are relative to "
        "full scale, so converting them to sound pressure (dB re 1 µPa) needs "
        "the hydrophone's sensitivity and the recorder's gain."
    )

    with st.expander("Transformed data"):
        st.dataframe(transformed.head(200), width="stretch")
        st.download_button(
            "Download transformed CSV",
            transformed.to_csv(index=False).encode(),
            file_name=f"{os.path.splitext(df.attrs.get('source', 'audio'))[0]}"
                      f"_{name.lower().replace(' ', '_')}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
