"""
Shared helpers for parsing the PAM Rodeo glider noise HDF5 files and for the per-mode/per-bin
noise analysis used across glider_data_explore.ipynb and glider_noise_stats_plots.ipynb.
"""
import numpy as np
import pandas as pd
import h5py
import seaborn as sns
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature


def inspect_h5_structure(group, indent=0):
    """Print type/shape/dtype for every item in an h5py group, to see why a flat loop over .keys() doesn't work."""
    for name, item in group.items():
        if isinstance(item, h5py.Group):
            print(' ' * indent + f'{name}/  (Group, not a Dataset - cannot be sliced with [:])')
            inspect_h5_structure(item, indent + 4)
        else:
            print(' ' * indent + f'{name}: shape={item.shape}, dtype={item.dtype}')


# 2D level matrices (time x frequency bin) paired with the 1D frequency vector
# used to label their columns, instead of reading each as its own single column
FREQ_PAIRS = {
    'decadeLevels': 'decadeFreqHz',
    'hybridMiliDecLevels': 'hybridDecFreqHz',
    'thirdoct': 'thirdOctFreqHz',
}


def build_noise_df(pam_noise):
    """
    Build a DataFrame from the PAM noise HDF5 file.

    The datasets under GliderRodeo are not uniform, so a flat loop over
    .keys() doesn't work:
    - 'Parameters' is a Group, not a Dataset, so it can't be sliced with [:]
      and is skipped here.
    - 'DateTime' is an object array of variable-length byte strings and
      needs elementwise decoding.
    - 'decadeLevels' / 'hybridMiliDecLevels' / 'thirdoct' are 2D
      (time x frequency) matrices; their columns are labeled using the
      paired *FreqHz vector rather than being treated as one time series.
      'hybridDecFreqHz' has 3 columns (band edges + center) - the middle
      column is used as the representative frequency.
    - Everything else (e.g. 'broadband') is a single time-varying column.
    """
    glider_group = pam_noise['GliderRodeo']

    freq_vectors = {}
    for freq_name in FREQ_PAIRS.values():
        fv = glider_group[freq_name][:]
        if fv.ndim == 2 and fv.shape[1] == 1:
            fv = fv[:, 0]
        elif fv.ndim == 2:
            # multi-column band-edge table (e.g. [low, center, high]) -
            # use the middle column as the representative/center frequency
            fv = fv[:, fv.shape[1] // 2]
        freq_vectors[freq_name] = fv

    columns = {}
    for name, item in glider_group.items():
        if not isinstance(item, h5py.Dataset):
            continue  # e.g. 'Parameters' group

        if name in FREQ_PAIRS.values():
            continue  # only used to label columns of the matching *Levels matrix

        data = item[:]

        if data.dtype == object:  # h5py variable-length strings -> array of bytes/str objects
            data = np.array([x.decode('utf-8') if isinstance(x, bytes) else x for x in data])
        elif data.dtype.kind == 'S':  # fixed-length bytes -> string
            data = data.astype(str)

        if data.ndim == 2 and data.shape[1] == 1:
            data = data[:, 0]

        if name in FREQ_PAIRS:
            freqs = freq_vectors[FREQ_PAIRS[name]]
            for i, f in enumerate(freqs):
                columns[f'{name}_{f:g}Hz'] = data[:, i]
        elif data.ndim == 1:
            columns[name] = data
        else:
            # unexpected extra 2D dataset - fall back to indexed columns
            for i in range(data.shape[1]):
                columns[f'{name}_{i}'] = data[:, i]

    noise_df = pd.DataFrame(columns)

    if 'DateTime' in noise_df.columns:
        noise_df['DateTime'] = pd.to_datetime(noise_df['DateTime'], errors='coerce')

    return noise_df


def compute_depth_mask_flag(df, dive_col='dive', depth_col='depth'):
    """
    Flag rows whose depth falls outside the 'good' range established by the PREVIOUS dive's
    own surface/bottom inflection points.

    For one dive/climb pair, the bottom inflection is the max depth reached (the turn from
    descent to ascent) and the surface inflection is the min depth (near-surface at the start
    and end) - e.g. for depths [0, 2, 3, 4, 5, 4, 3, 2, 1], the bottom inflection is 5.

    A dive's own rows can never be shallower/deeper than that same dive's own min/max, so
    comparing a dive's rows to its own inflection points would trivially always pass. Instead,
    each dive's rows are compared against the PREVIOUS dive's inflection points:
    - depth_mask_flag = 1 if shallower than the previous dive's surface inflection
    - depth_mask_flag = 1 if deeper than the previous dive's bottom inflection
    - depth_mask_flag = 0 otherwise (good range of data)

    The first dive has no previous dive to compare against, so it's left unflagged (0).

    Known limitation: a dive that legitimately goes much deeper/shallower than the immediately
    preceding one (e.g. at a mission-phase transition, like shallow-dives -> slow/deep-dives)
    will trip this - it's a dive-to-dive check, not a mode-aware one.
    """
    dive_bounds = df.groupby(dive_col)[depth_col].agg(surface_inflection='min', bottom_inflection='max')
    dive_bounds = dive_bounds.sort_index()
    prev_bounds = dive_bounds.shift(1)

    row_bounds = df[[dive_col]].join(prev_bounds, on=dive_col)
    flag = (df[depth_col] < row_bounds['surface_inflection']) | (df[depth_col] > row_bounds['bottom_inflection'])
    return flag.astype(int)


def make_bin_edges(series, width):
    """Fixed-width bin edges covering `series`'s full range, rounded outward to whole widths."""
    lo = np.floor(series.min() / width) * width
    hi = np.ceil(series.max() / width) * width + width
    return np.arange(lo, hi, width)


def setup_map_axes(ax, extent, left_labels=True):
    """
    Land/coastline/gridline boilerplate for a cartopy PlateCarree map axis - the same setup
    used for glider track maps in server_comparison_plots.ipynb. Caller still does its own
    ax.plot(..., transform=ccrs.PlateCarree()) calls for the actual data/styling.

    left_labels: set False for a panel sharing its y-axis with one to its left (e.g. in a
    side-by-side comparison), so the latitude labels aren't repeated on every panel.
    """
    land_10m = cfeature.NaturalEarthFeature('physical', 'land', '10m', edgecolor='face', facecolor='lightgray')
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(land_10m)
    ax.add_feature(cfeature.COASTLINE.with_scale('10m'))
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.left_labels = left_labels
    return ax


def plot_corr_matrix(df, variables, title, ax, cbar=True, annot_kws=None):
    """
    Pearson correlation heatmap for `variables` in `df` (pairwise-complete rows dropped),
    diverging RdBu_r colormap centered at 0. Draws into the given `ax` and returns the
    underlying correlation matrix (in case the caller wants the numbers too).
    """
    matrix = df[variables].dropna().corr()
    sns.heatmap(matrix, annot=True, fmt='.2f', cmap='RdBu_r', vmin=-1, vmax=1, ax=ax,
                cbar=cbar, annot_kws=annot_kws)
    ax.set_title(title)
    return matrix


def plot_spectrum_lines(freqs, groups, colors, title, ax=None, figsize=(8, 5),
                         legend_ncol=4, legend_fontsize=7, legend_anchor=-0.18):
    """
    Spectrum plot: frequency (log x-axis) vs SPL (y-axis, dB re: 1 uPa), one line per group.

    freqs: 1D array of frequencies (Hz), shared x-axis for every line.
    groups: {label: spl_values} - one line per entry. Skip empty groups before calling
            this rather than passing them in (nothing to plot for an empty group).
    colors: {label: color} - must have an entry for every key in `groups`.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    for label, values in groups.items():
        ax.plot(freqs, values, color=colors[label], label=str(label), linewidth=1)
    ax.set_xscale('log')
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('SPL (dB re: 1 μPa)')
    ax.set_title(title)
    ax.legend(fontsize=legend_fontsize, loc='upper center', bbox_to_anchor=(0.5, legend_anchor),
              ncol=legend_ncol)
    return ax


def plot_box_by_group(data_dict, colors, xlabel, ylabel, title, ax=None, figsize=(8, 5),
                       rotate_xticks=True):
    """
    Box plot: one box per group (dict key), colored per group. Each x-tick label includes
    that group's sample size (n=...) on its own line underneath.

    data_dict: {label: array-like of values} - one box per entry, in dict iteration order.
    colors: {label: color} - must have an entry for every key in `data_dict`.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    labels = list(data_dict.keys())
    data = [data_dict[label] for label in labels]
    tick_labels = [f'{label}\n(n={len(d):,})' for label, d in zip(labels, data)]
    bp = ax.boxplot(data, labels=tick_labels, showmeans=True, patch_artist=True)
    for patch, label in zip(bp['boxes'], labels):
        patch.set_facecolor(colors[label])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if rotate_xticks:
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
            tick.set_ha('right')
    return ax
