"""
Shared configuration for the PAM Rodeo glider noise analysis notebooks:
glider_data_explore.ipynb -> glider_noise_stats_plots.ipynb -> glider_noise_presentation.ipynb

Edit the values here instead of in the notebooks - this is the single place to change which
glider/deployment is being analyzed, where the raw data lives, or any analysis parameter.
"""
import os

# --- Deployment ---
GLIDER_ID = 'sg607'
DEPLOYMENT_DATE = '20260128'  # matches the date embedded in the raw filenames

# --- Environment: where does the raw data live? ---
# Override with an env var (e.g. `PAM_RODEO_ENV=jupyterhub`) instead of editing this file, so the
# same committed config works unchanged on JupyterHub and locally without commenting code in/out.
ENVIRONMENT = os.environ.get('PAM_RODEO_ENV', 'local')  # 'local' or 'jupyterhub'

if ENVIRONMENT == 'jupyterhub':
    _sci_dir = f'/home/jovyan/shared-public/GliderRodeo/{GLIDER_ID}_{DEPLOYMENT_DATE}'
    _noise_dir = f'/home/jovyan/shared-public/GliderRodeo/Noise/{GLIDER_ID}_{DEPLOYMENT_DATE}'
    PHASE_KEY_PATH = '/home/jovyan/shared-public/GliderRodeo/glider_rodeo_phase_key.xlsx'
else:
    _sci_dir = '.'
    _noise_dir = '.'
    PHASE_KEY_PATH = './glider_rodeo_phase_key.xlsx'

GLIDER_SCI_PATH = os.path.join(_sci_dir, f'{GLIDER_ID}_{DEPLOYMENT_DATE}_science_timeseries.csv')
PAM_NOISE_PATH = os.path.join(_noise_dir, f'{GLIDER_ID}_{DEPLOYMENT_DATE}.h5')

# --- Output - one folder per glider, shared by all three notebooks ---
OUTPUT_ROOT = './noise_analysis_outputs'
OUT_DIR = os.path.join(OUTPUT_ROOT, GLIDER_ID)

# Data (CSV/parquet/JSON) and figures (PNGs) are kept in separate subfolders so they don't
# get mixed together. The final .pptx is saved directly in OUT_DIR.
DATA_DIR = os.path.join(OUT_DIR, 'data')
FIGURES_DIR = os.path.join(OUT_DIR, 'figures')

# Created on import so every notebook can rely on these existing, rather than each one
# needing its own os.makedirs() call.
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

# --- Merging glider science data with PAM noise (glider_data_explore.ipynb) ---
NOISE_MERGE_TOLERANCE = '90s'  # pandas Timedelta string - max gap between a science row and its nearest PAM sample

# --- QC toggle ---
# Whether the QC step in glider_data_explore.ipynb (currently a placeholder) has been applied
# to this run's data. Recorded into summary_meta.json and surfaced on the presentation deck's
# title slide, so it's always obvious at a glance whether a given deck reflects QC'd data or not.
QC_APPLIED = False

# --- Mission phases to skip entirely in the per-mode plots/analysis (glider_noise_stats_plots.ipynb) ---
# e.g. 'recovery' only covers the last dive with barely any data - not worth a full set of
# spectrum/box/correlation plots for it. Doesn't affect whole-deployment (all-modes-combined) stats.
EXCLUDED_MODES = ['recovery']

# --- Binning science variables for the per-mode comparisons (glider_noise_stats_plots.ipynb) ---
BIN_VARS = ['temperature', 'salinity', 'density', 'soundVelocity', 'depth', 'latitude', 'longitude']
BIN_WIDTHS = {
    'temperature': 10,     # deg C
    'salinity': 0.5,       # psu
    'density': 2,          # kg/m3
    'soundVelocity': 5,    # m/s
    'depth': 100,          # m - dives go to ~1000 m here, smaller widths get too crowded
    'latitude': 0.05,      # deg - rough default, adjust once you see the printed bin count
    'longitude': 0.05,     # deg - rough default, adjust once you see the printed bin count
}
