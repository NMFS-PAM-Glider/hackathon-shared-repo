"""Streamlit front end for inspecting ocean-glider hydrophone recordings.

Run with:  streamlit run audio_vis/app.py

The page is one matrix of panels: a row per step of the transform chain, three
columns per row — what went into the step, what came out, and what the step
removed — every compatible axis linked, so a zoom anywhere moves all of them.
A chain of two or more steps closes with a cumulative row: the original file
against the final output.

The sidebar reads in the order the data flows.  **Input** picks the file and
the window, **Display** picks what goes on the Y axis of every panel, and
**Transform chain** is the pipeline itself, one block per step.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import streamlit as st

from chain import chain_controls, chain_key, final_result
from data import channel_columns, load_data, window_span
from ltsa_panel import render_ltsa_panel
from playback import render_playback
from plots import (
    VIEWS,
    axis_revisions,
    chain_figures,
    link_grid,
    window_label,
)

# DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  #   For running with data in the immediate folder above this one
# DATA_DIR = "/home/jovyan/shared-public/GliderRodeo/audio"
# DATA_DIR = "/home/aaron-mau/Code/ohw/2026/rodeo"
DATA_DIR = "/home/aaron-mau/Data/pam_rodeo"

# Where the .ltsa files live. Defaults to the folder holding the audio dir, so
# audio/ and the LTSAs can sit side by side under GliderRodeo.
LTSA_DIR = os.path.dirname(DATA_DIR.rstrip("/"))

# Header illustration, looked up beside this file so the app still runs if it
# is missing.
GLIDER_IMAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glider.png")


def view_controls(df) -> tuple[str, dict, bool]:
    """Pick what goes on the Y axis of every panel, plus that view's options.

    The view applies to the whole matrix: the chain is the same chain whether
    it is read as waveforms, spectra or spectrograms, so switching redraws all
    the rows at once rather than being chosen per step.

    Only the view itself stays on show.  Its settings are things you set once
    and leave, so they fold away into an expander instead of pushing the chain
    below them off the screen.
    """
    st.sidebar.header("Display")

    view = st.sidebar.selectbox(
        "View (Y axis)", list(VIEWS),
        help="Waveform: amplitude vs time. Spectrum: magnitude vs frequency. "
             "PSD: Welch power spectral density, an averaged and steadier "
             "spectrum. Spectrogram: frequency vs time, colored by level.",
    )

    opts: dict = {}
    with st.sidebar.expander(f"{view} settings", expanded=False):
        if view in ("Spectrum", "PSD"):
            if view == "Spectrum":
                opts["window"] = st.selectbox(
                    "FFT window", ["hann", "hamming", "blackman", "boxcar", "none"]
                )
            else:
                opts["psd_nperseg"] = int(st.select_slider(
                    "Segment length", [256, 512, 1024, 2048, 4096, 8192, 16384],
                    value=4096,
                    help="Welch averages over segments of this length: longer "
                         "resolves frequency better, shorter averages more of "
                         "them together and gives a smoother estimate.",
                ))
                opts["overlap_pct"] = float(
                    st.slider("Overlap (%)", 0, 90, 50, step=5)
                )
            opts["scale"] = st.selectbox("Magnitude scale", ["dB", "linear"])
            opts["log_x"] = st.checkbox("Log frequency axis", value=True)
        elif view == "Spectrogram":
            opts["channel"] = st.selectbox(
                "Channel", channel_columns(df),
                help="A spectrogram shows one channel at a time.",
            )
            opts["nperseg"] = int(st.select_slider(
                "FFT length", [256, 512, 1024, 2048, 4096, 8192], value=1024,
                help="Longer windows resolve frequency better, shorter ones time.",
            ))
            opts["overlap_pct"] = float(st.slider("Overlap (%)", 0, 90, 50, step=5))
            opts["dynamic_range"] = float(
                st.slider("Dynamic range (dB)", 20, 120, 60, step=5)
            )
            opts["colorscale"] = st.selectbox(
                "Color scale",
                ["Viridis", "Inferno", "Magma", "Cividis", "Turbo", "Greys"],
            )
            opts["residual_autoscale"] = st.checkbox(
                "Auto-scale residual colors", value=False,
                help="Off: each row's residual shares that row's color limits, "
                     "so how much energy the step removed is read directly "
                     "against its input. On: the residual is stretched to its "
                     "own range, which brings out a quiet residual but makes it "
                     "look as loud as the input.",
            )

        link_x = st.checkbox(
            "Link X axes", value=True,
            help="Pan or zoom any panel and every compatible panel follows.",
        )
    return view, opts, link_x


def main() -> None:
    st.set_page_config(page_title="Glider Audio Viewer", layout="wide")

    # The glider sits to the left of the title. vertical_alignment keeps the
    # two centred on each other rather than both pinned to the top.
    if os.path.exists(GLIDER_IMAGE):
        art, heading = st.columns([1, 3], vertical_alignment="center")
        art.image(GLIDER_IMAGE, width="stretch")
        heading.title("Glider Audio Viewer")
    else:
        st.title("Glider Audio Viewer")

    # The sidebar is built in this order, and the data flows through it the
    # same way: a file and a window, how to draw it, then what to do to it.
    df = load_data(DATA_DIR)                    # 1. Input
    view, opts, link_x = view_controls(df)      # 2. Display
    stages = chain_controls(df)                 # 3. Transform chain

    # 4. the matrix ---------------------------------------------------------
    rows = chain_figures(stages, view, opts)

    # Changing a step's settings must not throw away where you were looking, so
    # the zoom is tagged with what it depends on rather than with the chain's
    # contents — but it does carry the shape of the matrix, because adding or
    # removing a row renumbers every axis below it.
    x_revision, y_revision = axis_revisions(
        df, view, opts, transform_key=chain_key(stages), shape=f"{len(rows)}x3"
    )

    st.plotly_chart(
        link_grid(
            rows,
            link_x=link_x,
            # Frequency is the same quantity in every spectrogram panel, so the
            # Y axis is worth linking too; amplitude scales differ per panel.
            link_y=link_x and view == "Spectrogram",
            x_revision=x_revision,
            y_revision=y_revision,
            # Every panel is drawn from the same window, so it is captioned once
            # above them: the sliders otherwise change the data with no visible
            # effect, because each view rescales to whatever it is handed.
            window_note=window_label(df, view),
        ),
        width="stretch",
        config={"scrollZoom": True},
        # A stable key keeps the chart mounted across reruns, which is what lets
        # Plotly apply the new data to the existing axes instead of redrawing.
        key="panels",
    )
    st.caption(
        ("Axes are linked — pan, zoom or box-select in any panel and every "
         "panel measuring the same thing follows. " if link_x else "")
        + "Each row is one step: its input, its output, and what it removed. "
        + ("The last row compares the original input with the chain's final "
           "output. " if len(stages) >= 2 else "")
        + "Your zoom is kept when you retune a step; it resets when you change "
          "file, window, view, or the number of steps, and double-clicking "
          "resets it to the whole loaded window."
    )

    # 5. playback ----------------------------------------------------------
    # Only in the Spectrogram view: that is the panel you are reading when you
    # want to know what a mark in it actually sounds like.
    if view == "Spectrogram":
        render_playback(df, stages)

    # 6. summary ----------------------------------------------------------
    st.subheader("Summary")
    st.caption(
        "Statistics of the **input** window, in full-scale units: samples are "
        "normalized so ±1.0 is the loudest value the recorder can represent."
    )
    span = window_span(df)
    cols = st.columns(len(channel_columns(df)) + 2)
    cols[0].metric(
        "Window", f"{span['duration_s']:.2f} s",
        f"{span['start_s']:.2f}–{span['end_s']:.2f} s",
        delta_color="off",
        help="Length of signal held in memory, and where it sits in the file. "
             "Set by the Start and Window sliders.",
    )
    cols[1].metric(
        "Samples", f"{len(df):,}",
        help="Number of samples per channel in the loaded window "
             "(window length × sample rate).",
    )
    for col, ch in zip(cols[2:], channel_columns(df)):
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

    final = final_result(stages)
    with st.expander("Final output data"):
        if final is None:
            st.info("No step in the chain produced an output.")
        else:
            st.caption(f"Output of the chain: {' → '.join(s.name for s in stages)}")
            st.dataframe(final.head(200), width="stretch")
            last = [s for s in stages if s.ok][-1]
            st.download_button(
                "Download final CSV",
                final.to_csv(index=False).encode(),
                file_name=f"{os.path.splitext(df.attrs.get('source', 'audio'))[0]}"
                          f"_{last.name.lower().replace(' ', '_')}.csv",
                mime="text/csv",
            )

    # 7. deployment context ------------------------------------------------
    # Last on the page, and only in the Spectrogram view: the LTSA is frequency
    # against time, so it is the one view whose axes mean the same thing as the
    # panels above it.
    if view == "Spectrogram":
        render_ltsa_panel(df, LTSA_DIR, opts)


if __name__ == "__main__":
    main()
