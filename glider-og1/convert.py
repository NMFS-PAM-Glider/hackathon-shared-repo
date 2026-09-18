"""
File: glider-og1/convert.py

What it does: Converts glider deployments to OceanGliders OG1.0 NetCDF files.
    Each deployment is described by a YAML file in glider-og1/deployments/
    (which reader to use, which input files, platform/sensor metadata). The
    output is checked with the OG1 compliance checker after writing.

How to run (from the repository root):
    # on JupyterHub, straight from the shared data
    python glider-og1/convert.py --data-dir ~/shared-public/GliderRodeo --out-dir ~/og1 --all
    # locally, one or more deployments
    python glider-og1/convert.py --data-dir data --out-dir data/og1 sg607_20260128 stenella-20260128

Inputs:
    --data-dir   folder that holds one sub-folder per deployment (the `source_folder` in each YAML)
    deployments  names of YAML files in glider-og1/deployments/ (without .yaml), or --all
Outputs:
    <out-dir>/<platform_serial>_<start>_delayed.nc for each deployment, plus a
    compliance report printed to the terminal
"""

import argparse
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from glider_og1.build import build_dataset, write_og1  # noqa: E402
from glider_og1.readers import READERS  # noqa: E402
from glider_og1.validate import check, summarize  # noqa: E402

DEPLOYMENTS = HERE / "deployments"


def load_config(name):
    common = yaml.safe_load((DEPLOYMENTS / "_common.yaml").read_text()) or {}
    config = yaml.safe_load((DEPLOYMENTS / f"{name}.yaml").read_text())
    config["attributes"] = {**common.get("attributes", {}), **config.get("attributes", {})}
    config.setdefault("deployment_id", name)
    return config


def convert(name, data_dir, out_dir, run_check=True):
    config = load_config(name)
    reader = READERS[config["reader"]]
    folder = Path(data_dir).expanduser() / config["source_folder"]
    t0 = time.time()
    print(f"[{name}] reading {folder} with the '{config['reader']}' reader")
    glider = reader(folder, config["files"])
    ds = build_dataset(glider, config)
    out = write_og1(ds, Path(out_dir).expanduser())
    size_mb = out.stat().st_size / 1e6
    print(f"[{name}] wrote {out} ({ds.sizes['N_MEASUREMENTS']} rows, {size_mb:.1f} MB) in {time.time() - t0:.0f} s")
    if run_check:
        print(summarize(check(out)))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deployments", nargs="*", help="deployment YAML names (without .yaml)")
    parser.add_argument("--all", action="store_true", help="convert every deployment in glider-og1/deployments/")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--no-check", action="store_true", help="skip the OG1 compliance check")
    args = parser.parse_args()

    names = sorted(p.stem for p in DEPLOYMENTS.glob("*.yaml") if not p.stem.startswith("_")) if args.all \
        else args.deployments
    if not names:
        parser.error("give deployment names or --all")
    failed = []
    for name in names:
        try:
            convert(name, args.data_dir, args.out_dir, not args.no_check)
        except Exception as exc:  # keep going so one bad deployment does not stop the batch
            print(f"[{name}] FAILED: {type(exc).__name__}: {exc}")
            failed.append(name)
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
