"""
File: glider-og1/glider_og1/readers/__init__.py

What it does: Lists the available platform readers. To support a new glider
    type or file layout, add a module with a `read(folder, files)` function
    that returns a GliderData, and register it here.

How to run: imported by convert.py.

Inputs: none
Outputs: none
"""

from . import oceanscout, seaexplorer, seaglider, slocum

READERS = {
    "slocum": slocum.read,
    "seaglider": seaglider.read,
    "seaexplorer": seaexplorer.read,
    "oceanscout": oceanscout.read,
}
