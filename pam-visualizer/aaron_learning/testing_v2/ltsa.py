"""
Read and plot existing Triton-style .ltsa files.

This module only READS .ltsa files - it never writes or builds one.

Binary layout (verified against sg607_20260128_rodeo_example_5s_100Hz.ltsa):

  Header, 64 bytes
    0   4s    'LTSA'
    4   u8    version                     (4)
    5   3s    ftype                       ('xxx')
    8   u32   reserved / unidentified     (65 in the example file)
    12  u32   data_start, byte offset of the first spectral block
    16  f32   tave, seconds per time average
    20  f32   dfreq, Hz per frequency bin
    24  u32   fs, sample rate in Hz
    28  u32   nfft, FFT length  -> nfreq = nfft // 2 + 1
    32  u32   nrftimes, number of raw-file records
    36  u32   reserved / unidentified     (69387 in the example file)
    40  24x   zero padding

  Raw-file record table, nrftimes records of 104 bytes each, starting at 64
    0   6x u8  YY MM DD hh mm ss  (2-digit year, UTC)
    6   2x     padding
    8   u32    byteloc, offset of this file's spectral block
    12  u32    nave, number of time averages in this block
    16  88s    source filename, null padded

  Spectral data
    At each byteloc: nave * nfreq uint8 values, time-major, so
    reshape(nave, nfreq) gives one spectrum per row. Values are dB
    (RMS SPL, dB re 1 uPa) stored as unsigned integers.

Two fields at offsets 8 and 36 are not identified. Nothing here depends on
them; they are surfaced in .params as reserved_08 and reserved_36 so you can
compare across files and work out what they are.
"""

from __future__ import annotations

import os
import struct
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HEADER_SIZE = 64
RECORD_SIZE = 104
FILENAME_FIELD = 88

# The top frequency bin sits pinned near 249 dB and the one below it at 1 dB in
# the example file - both are edge artefacts of the FFT, not measurements. They
# are dropped by default because they otherwise dominate the colour scale.
DEFAULT_TRIM_TOP_BINS = 2


class LTSAError(RuntimeError):
    pass


class LTSAFile:
    """Lazy reader for a Triton-style .ltsa file."""

    def __init__(self, path, trim_top_bins: int = DEFAULT_TRIM_TOP_BINS):
        self.path = Path(path)
        if not self.path.is_file():
            raise LTSAError(f"File not found: {self.path}")

        self.filesize = os.path.getsize(self.path)
        self.trim_top_bins = int(trim_top_bins)

        self._read_header()
        self._read_records()
        self._build_time_index()

        self._mmap = None  # opened on first data read

    # ------------------------------------------------------------------
    # header and record table
    # ------------------------------------------------------------------

    def _read_header(self):
        with self.path.open("rb") as handle:
            raw = handle.read(HEADER_SIZE)

        if len(raw) < HEADER_SIZE:
            raise LTSAError("File is too short to contain an LTSA header.")
        if raw[0:4] != b"LTSA":
            raise LTSAError(f"Not an LTSA file - magic bytes were {raw[0:4]!r}.")

        self.version = raw[4]
        self.ftype = raw[5:8].decode("ascii", errors="replace")
        self.reserved_08 = struct.unpack_from("<I", raw, 8)[0]
        self.data_start = struct.unpack_from("<I", raw, 12)[0]
        self.tave = struct.unpack_from("<f", raw, 16)[0]
        self.dfreq = struct.unpack_from("<f", raw, 20)[0]
        self.fs = struct.unpack_from("<I", raw, 24)[0]
        self.nfft = struct.unpack_from("<I", raw, 28)[0]
        self.nrftimes = struct.unpack_from("<I", raw, 32)[0]
        self.reserved_36 = struct.unpack_from("<I", raw, 36)[0]

        if self.nfft <= 0:
            raise LTSAError(f"Implausible nfft in header: {self.nfft}")

        self.nfreq_full = self.nfft // 2 + 1
        self.nfreq = self.nfreq_full - self.trim_top_bins

        if self.nfreq < 2:
            raise LTSAError("trim_top_bins removed nearly every frequency bin.")

        self.freq_full = np.arange(self.nfreq_full, dtype=np.float64) * self.dfreq
        self.freq = self.freq_full[: self.nfreq]

    def _read_records(self):
        expected = HEADER_SIZE + self.nrftimes * RECORD_SIZE
        if expected > self.filesize:
            raise LTSAError(
                f"Header claims {self.nrftimes} records ({expected} bytes) but the "
                f"file is only {self.filesize} bytes."
            )

        with self.path.open("rb") as handle:
            handle.seek(HEADER_SIZE)
            blob = handle.read(self.nrftimes * RECORD_SIZE)

        starts, bytelocs, naves, names = [], [], [], []

        for i in range(self.nrftimes):
            base = i * RECORD_SIZE
            yy, mm, dd, hh, mi, ss = blob[base : base + 6]
            byteloc = struct.unpack_from("<I", blob, base + 8)[0]
            nave = struct.unpack_from("<I", blob, base + 12)[0]
            name = (
                blob[base + 16 : base + 16 + FILENAME_FIELD]
                .split(b"\x00")[0]
                .decode("latin-1")
            )

            year = 2000 + yy if yy < 70 else 1900 + yy
            try:
                stamp = datetime(year, mm, dd, hh, mi, ss)
            except ValueError:
                stamp = pd.NaT

            starts.append(stamp)
            bytelocs.append(byteloc)
            naves.append(nave)
            names.append(name)

        self.records = pd.DataFrame(
            {
                "start": pd.to_datetime(starts),
                "byteloc": np.asarray(bytelocs, dtype=np.int64),
                "nave": np.asarray(naves, dtype=np.int64),
                "filename": names,
            }
        )

        bad = self.records["start"].isna().sum()
        if bad:
            print(f"  ! {bad} record(s) had an unreadable timestamp and were dropped")
            self.records = self.records.dropna(subset=["start"]).reset_index(drop=True)

        if self.records.empty:
            raise LTSAError("No usable raw-file records in this LTSA.")

        # Sanity check: the last block should end exactly at end of file.
        last = self.records.iloc[-1]
        predicted = int(last["byteloc"] + last["nave"] * self.nfreq_full)
        self.layout_ok = predicted == self.filesize
        if not self.layout_ok:
            print(
                f"  ! layout check failed: last block ends at {predicted} but the "
                f"file is {self.filesize} bytes. Data may be misread."
            )

    def _build_time_index(self):
        """One timestamp per stored time average."""
        naves = self.records["nave"].to_numpy()
        starts = self.records["start"].to_numpy().astype("datetime64[ns]")

        offsets = np.concatenate([np.arange(n) for n in naves])
        repeated = np.repeat(starts, naves)
        step_ns = np.int64(round(self.tave * 1e9))

        self.times = pd.DatetimeIndex(repeated + offsets * np.timedelta64(step_ns, "ns"))
        self.nbins = len(self.times)

        # Byte offset of every individual spectrum.
        block_starts = np.repeat(self.records["byteloc"].to_numpy(), naves)
        self._bin_offsets = block_starts + offsets * self.nfreq_full

    # ------------------------------------------------------------------
    # data access
    # ------------------------------------------------------------------

    def _map(self):
        if self._mmap is None:
            self._mmap = np.memmap(self.path, dtype=np.uint8, mode="r")
        return self._mmap

    def _freq_slice(self, fmin, fmax):
        """Column range covering [fmin, fmax]. Subsetting here avoids reading
        bins we are about to throw away, which is most of them when zoomed in."""
        lo = 0 if fmin is None else int(np.searchsorted(self.freq, fmin, "left"))
        hi = self.nfreq if fmax is None else int(
            np.searchsorted(self.freq, fmax, "right")
        )
        lo = max(0, min(lo, self.nfreq - 1))
        hi = max(lo + 1, min(hi, self.nfreq))
        return lo, hi

    def _time_index(self, start, end):
        mask = np.ones(self.nbins, dtype=bool)
        if start is not None:
            mask &= self.times >= pd.Timestamp(start)
        if end is not None:
            mask &= self.times <= pd.Timestamp(end)
        if not mask.any():
            raise LTSAError("No time bins fall inside the requested window.")
        return np.flatnonzero(mask)

    def _gather(self, idx, lo, hi):
        """Pull spectra for the given bin indices and column range."""
        data = self._map()
        cols = np.arange(lo, hi, dtype=np.int64)
        rows = self._bin_offsets[idx]
        return data[rows[:, None] + cols[None, :]]

    def read(
        self,
        start=None,
        end=None,
        averaging_period=None,
        fmin=None,
        fmax=None,
        chunk_bins=4096,
        max_raw_bins=120_000,
    ):
        """
        Return (times, freq, psd_dB).

        start, end       : anything pandas can parse, or None for no limit
        averaging_period : pandas offset alias such as '5min'. None keeps the
                           native tave resolution.
        fmin, fmax       : frequency window in Hz, applied during the read
        chunk_bins       : native bins held in memory at once while averaging
        max_raw_bins     : guard against an unaveraged read blowing up memory

        Averaging is done in linear space and converted back to dB.
        """
        idx = self._time_index(start, end)
        lo, hi = self._freq_slice(fmin, fmax)
        freq = self.freq[lo:hi]

        if averaging_period is None:
            if len(idx) > max_raw_bins:
                raise LTSAError(
                    f"{len(idx)} native bins requested. Pass an averaging_period, "
                    f"narrow the window, or raise max_raw_bins."
                )
            return self.times[idx], freq, self._gather(idx, lo, hi).astype(np.float32)

        times = self.times[idx]
        origin = times[0].floor(averaging_period)
        step = pd.Timedelta(averaging_period)
        labels = ((times - origin) // step).astype(np.int64).to_numpy()

        # times are sorted, so labels are non-decreasing and each output bin is
        # one contiguous run. That lets us use reduceat instead of add.at.
        starts = np.flatnonzero(np.r_[True, labels[1:] != labels[:-1]])
        group_labels = labels[starts]
        group_sizes = np.diff(np.r_[starts, len(labels)])
        n_out = len(starts)

        totals = np.empty((n_out, hi - lo), dtype=np.float64)

        g0 = 0
        while g0 < n_out:
            g1, taken = g0, 0
            while g1 < n_out and (taken == 0 or taken + group_sizes[g1] <= chunk_bins):
                taken += group_sizes[g1]
                g1 += 1

            bin_lo = starts[g0]
            bin_hi = starts[g1] if g1 < n_out else len(labels)

            block = self._gather(idx[bin_lo:bin_hi], lo, hi).astype(np.float64)
            np.power(10.0, block / 10.0, out=block)

            totals[g0:g1] = np.add.reduceat(block, starts[g0:g1] - bin_lo, axis=0)
            g0 = g1

        totals /= group_sizes[:, None]
        psd = (10.0 * np.log10(totals)).astype(np.float32)
        out_times = pd.DatetimeIndex(origin + group_labels * step)

        return out_times, freq, psd

    def estimate_bins(self, start=None, end=None, averaging_period=None) -> int:
        """How many output bins a read would produce, without reading anything."""
        idx = self._time_index(start, end)
        if averaging_period is None:
            return len(idx)
        times = self.times[idx]
        origin = times[0].floor(averaging_period)
        step = pd.Timedelta(averaging_period)
        labels = ((times - origin) // step).astype(np.int64).to_numpy()
        return int(np.count_nonzero(np.r_[True, labels[1:] != labels[:-1]]))

    # ------------------------------------------------------------------
    # metadata
    # ------------------------------------------------------------------

    @property
    def params(self) -> dict:
        """Everything needed to describe how this LTSA was computed."""
        return {
            "source file": self.path.name,
            "LTSA version": self.version,
            "source type": self.ftype,
            "sample rate (Hz)": int(self.fs),
            "FFT length": int(self.nfft),
            "frequency bin width (Hz)": float(self.dfreq),
            "time average (s)": float(self.tave),
            "frequency bins stored": int(self.nfreq_full),
            "frequency bins used": int(self.nfreq),
            "top bins trimmed": int(self.trim_top_bins),
            "frequency range (Hz)": f"{self.freq[0]:.0f} - {self.freq[-1]:.0f}",
            "raw files": int(len(self.records)),
            "time bins": int(self.nbins),
            "start (UTC)": self.times[0].strftime("%Y-%m-%d %H:%M:%S"),
            "end (UTC)": self.times[-1].strftime("%Y-%m-%d %H:%M:%S"),
            "duration": str(self.times[-1] - self.times[0]),
            "layout check": "passed" if self.layout_ok else "FAILED",
            "reserved_08": int(self.reserved_08),
            "reserved_36": int(self.reserved_36),
        }

    def params_text(self, extra: dict | None = None, per_line: int = 3) -> str:
        """The params dict laid out as a compact block for a figure footer."""
        items = dict(self.params)
        if extra:
            items.update(extra)

        pairs = [f"{k}: {v}" for k, v in items.items()]
        lines = [
            "    |    ".join(pairs[i : i + per_line])
            for i in range(0, len(pairs), per_line)
        ]
        return "\n".join(lines)

    def __repr__(self):
        return (
            f"<LTSAFile {self.path.name} | {self.fs} Hz | {self.tave:g} s "
            f"x {self.dfreq:g} Hz | {self.nbins} bins>"
        )



def parse_audio_time(name):
    """
    UTC start time from an audio filename, using the glider convention where
    the date is the second-to-last underscore field (YYMMDD) and the time is
    the last one (HHMMSS):

        stenella_20260128_WISPR_260207_160803.flac -> 2026-02-07 16:08:03

    Returns a pandas Timestamp, or None if the name does not match.
    """
    stem = Path(str(name)).stem
    fields = stem.split("_")
    if len(fields) < 2:
        return None

    date_field, time_field = fields[-2], fields[-1]
    if not (len(date_field) == 6 and date_field.isdigit()):
        return None
    if not (len(time_field) == 6 and time_field.isdigit()):
        return None

    yy, mm, dd = int(date_field[:2]), int(date_field[2:4]), int(date_field[4:6])
    hh, mi, ss = int(time_field[:2]), int(time_field[2:4]), int(time_field[4:6])
    year = 2000 + yy if yy < 70 else 1900 + yy

    try:
        return pd.Timestamp(datetime(year, mm, dd, hh, mi, ss))
    except ValueError:
        return None


def locate_audio_file(ltsa, name, duration_s=None):
    """
    Work out where an audio file sits inside an LTSA.

    Returns a dict with:
        time        the file's start time, or None if the name would not parse
        end         start + duration_s, when a duration is given
        in_range    True if it falls inside the LTSA's overall span
        message     a short human-readable verdict
    """
    stamp = parse_audio_time(name)

    if stamp is None:
        return {
            "time": None, "end": None, "in_range": False,
            "message": f"Could not read a date/time from '{Path(str(name)).name}'.",
        }

    t0, t1 = ltsa.times[0], ltsa.times[-1]
    in_range = t0 <= stamp <= t1
    stop = stamp + pd.Timedelta(seconds=duration_s) if duration_s else None

    if in_range:
        message = f"{stamp:%Y-%m-%d %H:%M:%S} UTC, inside this LTSA."
    else:
        gap = (t0 - stamp) if stamp < t0 else (stamp - t1)
        side = "before the start of" if stamp < t0 else "after the end of"
        message = (
            f"{stamp:%Y-%m-%d %H:%M:%S} UTC is {gap} {side} this LTSA "
            f"({t0:%Y-%m-%d %H:%M} to {t1:%Y-%m-%d %H:%M})."
        )

    return {"time": stamp, "end": stop, "in_range": in_range, "message": message}


# ----------------------------------------------------------------------
# plotting
# ----------------------------------------------------------------------


def plot_ltsa(
    ltsa,
    averaging_period="5min",
    start=None,
    end=None,
    fmin=None,
    fmax=None,
    title=None,
    save_path=None,
    dpi=300,
    log_freq=False,
    cmap="cubehelix",
    clim=None,
    show_params=True,
    mark_time=None,
    mark_end=None,
    mark_label=None,
    mark_color="red",
    fig=None,
):
    """
    Plot an LTSAFile, with the computation parameters printed below the axes.

    ltsa             : LTSAFile, or a path to a .ltsa file
    averaging_period : pandas offset alias, e.g. '5min'. None for native tave.
    start, end       : time window to plot
    fmin, fmax       : frequency window in Hz
    clim             : (vmin, vmax) in dB. None auto-scales to the 2nd-98th
                       percentile, which is far more readable than min-max.
    mark_time        : a timestamp, or an audio filename to parse one from,
                       drawn as a vertical marker line
    mark_end         : end of the marked file, drawn as a shaded band instead
                       of a bare line when the span is wide enough to see
    mark_label       : text above the marker. Defaults to the filename when
                       mark_time was given as one.
    show_params      : print the parameter block under the figure
    fig              : draw into an existing figure (used by Streamlit)
    """
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    if not isinstance(ltsa, LTSAFile):
        ltsa = LTSAFile(ltsa)

    times, freq, psd = ltsa.read(
        start=start, end=end, averaging_period=averaging_period,
        fmin=fmin, fmax=fmax,
    )

    if fig is None:
        fig = plt.figure(figsize=(12, 7.5))
    ax = fig.add_subplot(111)

    if clim is None:
        clim = (
            float(np.nanpercentile(psd, 2)),
            float(np.nanpercentile(psd, 98)),
        )

    step = (
        pd.Timedelta(averaging_period)
        if averaging_period
        else pd.Timedelta(seconds=ltsa.tave)
    )
    t_edges = mdates.date2num(times.append(pd.DatetimeIndex([times[-1] + step])))
    f_edges = np.concatenate([freq, [freq[-1] + ltsa.dfreq]])

    pcm = ax.pcolormesh(
        t_edges, f_edges, psd.T, shading="flat", cmap=cmap,
        vmin=clim[0], vmax=clim[1],
    )

    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Frequency (Hz)")
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))

    if log_freq:
        positive = freq[freq > 0]
        if positive.size == 0:
            raise LTSAError("No positive frequency bins; cannot use a log scale.")
        ax.set_yscale("log")
        ax.set_ylim(positive.min(), freq.max())
    else:
        ax.set_ylim(freq.min(), freq.max())

    marker_note = None
    if mark_time is not None:
        label = mark_label
        stamp = mark_time

        if not isinstance(stamp, (pd.Timestamp, datetime)):
            parsed = parse_audio_time(stamp)
            if label is None:
                label = Path(str(stamp)).name
            stamp = parsed

        if stamp is None:
            marker_note = f"marker: could not parse a time from {mark_label or mark_time}"
        else:
            stamp = pd.Timestamp(stamp)
            lo, hi = times[0], times[-1] + step

            if not (lo <= stamp <= hi):
                marker_note = (
                    f"marker: {stamp:%Y-%m-%d %H:%M:%S} is outside the plotted window"
                )
            else:
                # A 60 s file on a multi-day axis is far under one pixel, so the
                # band only gets drawn when it is actually wide enough to see.
                drawn_band = False
                if mark_end is not None:
                    span = pd.Timestamp(mark_end) - stamp
                    if span > (hi - lo) / 400:
                        ax.axvspan(
                            mdates.date2num(stamp), mdates.date2num(pd.Timestamp(mark_end)),
                            color=mark_color, alpha=0.25, lw=0, zorder=5,
                        )
                        drawn_band = True

                if not drawn_band:
                    ax.axvline(
                        mdates.date2num(stamp), color=mark_color,
                        lw=1.4, alpha=0.9, zorder=6,
                    )

                if label:
                    # Inside the axes rather than above, so it cannot collide
                    # with the title. Nudged left near the right-hand edge.
                    frac = (stamp - lo) / (hi - lo)
                    ha = "right" if frac > 0.85 else "left" if frac < 0.15 else "center"
                    ax.annotate(
                        label,
                        xy=(mdates.date2num(stamp), 0.995),
                        xycoords=("data", "axes fraction"),
                        xytext=(0, -4), textcoords="offset points",
                        ha=ha, va="top", fontsize=7.5, color=mark_color,
                        zorder=7,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white",
                                  ec=mark_color, lw=0.6, alpha=0.85),
                    )

    cbar = fig.colorbar(pcm, ax=ax, pad=0.015)
    cbar.set_label(r"RMS SPL (dB re 1 $\mu$Pa)")

    if title:
        ax.set_title(title)

    ax.grid(False)
    ax.tick_params(direction="out", top=False, right=False)

    if show_params:
        text = ltsa.params_text(
            extra={
                "plot averaging": averaging_period or f"native ({ltsa.tave:g} s)",
                "colour limits (dB)": f"{clim[0]:.1f} to {clim[1]:.1f}",
                "plotted bins": len(times),
                **({"marker": marker_note} if marker_note else {}),
            }
        )
        fig.subplots_adjust(bottom=0.26)
        fig.text(
            0.01, 0.005, text,
            ha="left", va="bottom", fontsize=7.5, family="monospace",
            linespacing=1.6,
        )
    else:
        fig.tight_layout()

    if save_path:
        save_dir = os.path.dirname(str(save_path))
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")

    return fig


# ----------------------------------------------------------------------
# export, for handing the matrix to R or anything else
# ----------------------------------------------------------------------


def export(ltsa, out_path, averaging_period="5min", start=None, end=None, fmt="csv"):
    """
    Write an averaged LTSA to disk in a format other tools can read.

    Useful for archiving a reduced LTSA or handing it to a collaborator.
    fmt = 'csv'      -> portable, no extra dependencies
          'parquet'  -> smaller and typed (needs pyarrow installed)
          'npz'      -> numpy native, smallest for round-tripping
    Column names are the frequencies in Hz; the index/first column is time.
    """
    times, freq, psd = ltsa.read(start=start, end=end, averaging_period=averaging_period)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "npz":
        np.savez_compressed(
            out_path, times=times.values.astype("datetime64[s]"), freq=freq, psd=psd
        )
    else:
        frame = pd.DataFrame(psd, columns=[f"{f:.0f}" for f in freq])
        frame.insert(0, "time_utc", times)
        if fmt == "parquet":
            frame.to_parquet(out_path, index=False)
        elif fmt == "csv":
            frame.to_csv(out_path, index=False)
        else:
            raise LTSAError(f"Unknown format: {fmt}")

    # Parameters travel alongside, so the plot can be annotated downstream.
    meta_path = out_path.with_suffix(".params.csv")
    pd.DataFrame(
        {"parameter": list(ltsa.params), "value": [str(v) for v in ltsa.params.values()]}
    ).to_csv(meta_path, index=False)

    print(f"Wrote {out_path}  ({len(times)} x {len(freq)})")
    print(f"Wrote {meta_path}")
    return out_path, meta_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        sys.exit("usage: python ltsa.py <file.ltsa> [averaging_period] [out.png]")

    ltsa = LTSAFile(sys.argv[1])
    print(ltsa)
    for key, value in ltsa.params.items():
        print(f"  {key:26s} {value}")

    period = sys.argv[2] if len(sys.argv) > 2 else "5min"
    out = sys.argv[3] if len(sys.argv) > 3 else None
    plot_ltsa(ltsa, averaging_period=period, save_path=out,
              title=Path(sys.argv[1]).stem)
    if out:
        print(f"\nSaved {out}")
