"""
File: glider-og1/glider_og1/variables.py

What it does: The single registry of every variable the converter can write,
    with its OG1 name, units and CF/OG1 attributes. Readers rename their native
    columns to these names (in these units); build.py copies the attributes.

How to run: imported by the other modules, not run directly.

Inputs: none
Outputs: none

Names marked og1=True exist in the OG1 parameter vocabulary
(http://vocab.nerc.ac.uk/collection/OG1/current/). The rest are engineering
variables that OG1 does not (yet) define; they follow the same UPPER_CASE style
and carry no `vocabulary` attribute, so it is obvious they are local additions.
"""

OG1_VOCAB = "https://vocab.nerc.ac.uk/collection/OG1/current/{name}/"

QC_ATTRS = {
    "long_name": "quality flag",
    "flag_values": [0, 1, 2, 3, 4],
    "flag_meanings": "no_qc_performed good_data probably_good_data probably_bad_data bad_data",
}

# name: (og1, units, long_name, standard_name or None, sensor type or None)
#   sensor type links the variable to a SENSOR_<type>_<serial> variable.
_REGISTRY = {
    # --- coordinates ---------------------------------------------------------
    "LATITUDE": (True, "degrees_north", "latitude of each measurement", "latitude", None),
    "LONGITUDE": (True, "degrees_east", "longitude of each measurement", "longitude", None),
    "DEPTH": (False, "m", "depth of each measurement, positive down", "depth", None),
    "DEPTH_Z": (False, "m", "depth of each measurement, positive up (-DEPTH)", "height", None),
    "LATITUDE_GPS": (True, "degrees_north", "latitude of each GPS fix", "latitude", None),
    "LONGITUDE_GPS": (True, "degrees_east", "longitude of each GPS fix", "longitude", None),
    # --- CTD -----------------------------------------------------------------
    "PRES": (True, "dbar", "sea water pressure, equals 0 at sea level", "sea_water_pressure", "CTD"),
    "TEMP": (True, "degree_Celsius", "sea temperature in-situ ITS-90 scale", "sea_water_temperature", "CTD"),
    "CNDC": (True, "mS cm-1", "electrical conductivity of the water body", "sea_water_electrical_conductivity", "CTD"),
    "PSAL": (True, "1", "practical salinity of the water body", "sea_water_practical_salinity", "CTD"),
    "DENSITY": (True, "kg m-3", "sea water density", "sea_water_density", "CTD"),
    "THETA": (True, "degree_Celsius", "sea water potential temperature", "sea_water_potential_temperature", "CTD"),
    "POTDENS": (False, "kg m-3", "sea water potential density", "sea_water_potential_density", "CTD"),
    "SOUNDVEL": (True, "m s-1", "sound velocity in the water body", "speed_of_sound_in_sea_water", "CTD"),
    "TEMP_CNDC": (True, "degree_Celsius", "internal temperature of the conductivity cell", None, "CTD"),
    # --- attitude and depth (vocabulary) ----------------------------------------
    "GLIDER_DEPTH": (True, "m", "depth of the glider from its navigation pressure sensor", None, None),
    "PRES_ENG": (True, "dbar", "pressure from the glider's navigation (non-CTD) sensor", None, None),
    "GLIDER_PITCH": (True, "degree", "glider pitch, positive nose up", "platform_pitch", None),
    "GLIDER_ROLL": (True, "degree", "glider roll, positive starboard wing down", "platform_roll", None),
    "GLIDER_HEADING": (True, "degree", "glider heading relative to magnetic north", "platform_orientation", None),
    "OIL_VOL": (True, "cm3", "oil volume in the external bladder (positive = more buoyant)", None, None),
    "GLIDER_RELATIVE_VBD": (True, "cm3", "variable buoyancy device volume relative to neutral", None, None),
    "ALTITUDE": (True, "m", "height of the glider above the sea floor from altimeter", None, None),
    "WATERCURRENTS_U": (True, "m s-1", "eastward depth-averaged current between surfacings", "eastward_sea_water_velocity", None),
    "WATERCURRENTS_V": (True, "m s-1", "northward depth-averaged current between surfacings", "northward_sea_water_velocity", None),
    # --- glider flight / engineering (not in the OG1 vocabulary) ----------------
    "GLIDER_VERT_VELO_DZDT": (False, "m s-1", "glider vertical velocity from dDEPTH_Z/dt, positive up", None, None),
    "GLIDER_VERT_VELO_MODEL": (False, "m s-1", "glider vertical velocity from flight model, positive up", None, None),
    "GLIDER_HORZ_VELO_MODEL": (False, "m s-1", "glider horizontal speed through water from flight model", None, None),
    "GLIDER_SPEED_MODEL": (False, "m s-1", "glider total speed through water from flight model", None, None),
    "GLIDE_ANGLE_MODEL": (False, "degree", "glide angle from flight model", None, None),
    "BUOYANCY_MODEL": (False, "g", "glider buoyancy from flight model, corrected for compression", None, None),
    "GLIDER_SPEED": (False, "m s-1", "glider horizontal speed through water reported by the glider", None, None),
    "GLIDER_SPEED_AVG": (False, "m s-1", "running mean glider speed over the current dive or climb", None, None),
    "GLIDER_DEPTH_RATE": (False, "m s-1", "rate of change of depth reported by the glider, positive down", None, None),
    "GLIDER_PITCH_COMMANDED": (False, "degree", "commanded glider pitch", None, None),
    "GLIDER_HEADING_COMMANDED": (False, "degree", "desired heading set by the flight controller", None, None),
    "OIL_VOL_COMMANDED": (False, "cm3", "commanded oil volume", None, None),
    "FIN_ANGLE": (False, "degree", "measured rudder/fin angle", None, None),
    "FIN_ANGLE_COMMANDED": (False, "degree", "commanded rudder/fin angle", None, None),
    "GLIDER_PITCH_MASS_POSITION": (False, "m", "measured position of the pitch battery/mass", None, None),
    "BALLAST_POSITION": (False, "cm3", "measured ballast (buoyancy) position", None, None),
    "BALLAST_COMMANDED": (False, "cm3", "commanded ballast (buoyancy) position", None, None),
    "PITCH_MOTOR_POSITION": (False, "mm", "measured linear (pitch) motor position", None, None),
    "PITCH_MOTOR_COMMANDED": (False, "mm", "commanded linear (pitch) motor position", None, None),
    "ROLL_MOTOR_POSITION": (False, "degree", "measured angular (roll) motor position", None, None),
    "ROLL_MOTOR_COMMANDED": (False, "degree", "commanded angular (roll) motor position", None, None),
    "BATTERY_VOLTAGE": (False, "V", "measured battery voltage", None, None),
    "BATTERY_CURRENT": (False, "A", "instantaneous current draw", None, None),
    "BATTERY_CHARGE_USED": (False, "A h", "integrated charge used this mission", None, None),
    "BATTERY_CHARGE_USED_TOTAL": (False, "A h", "persistent integrated charge used since battery install", None, None),
    "INTERNAL_PRESSURE": (False, "Pa", "pressure inside the glider hull", None, None),
    "INTERNAL_HUMIDITY": (False, "percent", "relative humidity inside the glider hull", None, None),
    "INTERNAL_TEMPERATURE": (False, "degree_Celsius", "temperature inside the glider hull", None, None),
    "STORAGE_USED": (False, "MB", "data storage used on the acoustic/science recorder", None, None),
    "STORAGE_USED_SSD": (False, "MB", "data storage used on the solid-state drive", None, None),
    "DIVE_NUMBER": (False, "1", "dive number as reported by the glider or its processing", None, None),
    "NAV_STATE": (False, "1", "glider navigation state code as reported by the glider (see flag_meanings)", None, None),
}

# Mission-structure variables built by derive.py (OG1 section "phase & segment").
STRUCTURE_ATTRS = {
    "PHASE": {
        "long_name": "behavior of the glider at sea",
        "phase_vocabulary": "https://github.com/OceanGlidersCommunity/OG-format-user-manual/blob/main/vocabularyCollection/phase.md",
        "flag_values": [0, 1, 2, 3, 4, 5, 6, 7],
        "flag_meanings": "unknown ascent descent surfacing parking inflection propelled transition",
    },
    "PROFILE_NUMBER": {
        "long_name": "Identifier of numbered profile within the dataset",
        "units": "1",
        "profile_number_calculation_method": (
            "Increments by one each time the glider starts an ascending or descending profile. "
            "Rows between profiles keep the number of the preceding profile (0 before the first), "
            "matching the OceanGliders example files used by glidertest; use PROFILE_DIRECTION != 0 "
            "to select only the ascending/descending part."
        ),
    },
    "PROFILE_DIRECTION": {
        "long_name": "Vertical direction of profile",
        "profile_direction_calculation_method": "1 when descending, -1 when ascending, otherwise 0",
        "flag_values": [-1, 0, 1],
        "flag_meanings": "ascending not_profiling descending",
    },
    "SEGMENT_NUMBER": {
        "long_name": "Identifier of numbered segment (data between two surfacings)",
        "segment_number_calculation_method": "Increments by one each time the glider leaves the surface phase",
    },
}

# Variables that get a <NAME>_QC companion (all zeros = no QC performed).
QC_VARIABLES = ["TIME", "LATITUDE", "LONGITUDE", "DEPTH", "PRES", "TEMP", "CNDC", "PSAL", "PHASE"]


def attrs_for(name):
    """CF/OG1 attributes for a registered variable name."""
    if name in STRUCTURE_ATTRS:
        return dict(STRUCTURE_ATTRS[name])
    og1, units, long_name, standard_name, _ = _REGISTRY[name]
    attrs = {"long_name": long_name, "units": units}
    if standard_name:
        attrs["standard_name"] = standard_name
    if og1:
        attrs["vocabulary"] = OG1_VOCAB.format(name=name)
    return attrs


def sensor_type_for(name):
    """Sensor type (e.g. 'CTD') that measures this variable, or None."""
    return _REGISTRY[name][4] if name in _REGISTRY else None


def is_registered(name):
    return name in _REGISTRY or name in STRUCTURE_ATTRS


def registered_names():
    return list(_REGISTRY) + list(STRUCTURE_ATTRS)
