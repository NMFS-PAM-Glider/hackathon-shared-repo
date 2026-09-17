"""The transform chain: a series of functions, each fed by the one above it.

The app no longer applies a single transform.  It holds an ordered list of
*steps*, and the output of step N is the input of step N+1:

    file ──▶ [1. High-pass] ──▶ [2. Notch] ──▶ [3. Envelope] ──▶ final

Running the chain produces one :class:`Stage` per step, which is also one row
of the plot matrix in ``plots.chain_figures``: the stage's ``source`` is the
left panel, its ``result`` the middle one, and the difference between them the
residual on the right.

The step list lives in ``st.session_state`` so the "+" button can grow it
between reruns.  Each step keeps a ``uid`` that never changes, because widget
keys are built from it — indexing by position instead would hand step 3's
settings to step 2 the moment step 2 was deleted.

Widgets and evaluation are interleaved on purpose (see :func:`chain_controls`):
a parameter's bounds depend on the frame reaching that step -- a cutoff cannot
exceed Nyquist, and Nyquist itself changes the moment a Downsample appears
earlier in the chain -- so each step has to be run before the next one's
widgets can be drawn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from transformers import apply_transform, get_transform, list_transforms

STEPS_KEY = "chain_steps"
UID_KEY = "chain_next_uid"

# What a freshly added step starts as: the identity, so adding a row never
# changes the signal until a function is actually picked for it.
DEFAULT_STEP = "Passthrough"


@dataclass
class Stage:
    """One link of the chain — and one row of the plot matrix.

    ``source`` is what reached this step, ``result`` what it produced.  A stage
    that could not run carries ``error`` instead, and everything downstream of
    it carries a ``blocked`` message: the chain is a pipeline, so one broken
    step stops the rest rather than silently skipping it.
    """

    index: int                      # 1-based position in the chain
    uid: int                        # stable across reorder/removal
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    source: pd.DataFrame | None = None
    result: pd.DataFrame | None = None
    error: str | None = None
    source_label: str = ""

    @property
    def label(self) -> str:
        return f"{self.index}. {self.name}"

    @property
    def ok(self) -> bool:
        return self.result is not None


# --------------------------------------------------------------------------
# session state
# --------------------------------------------------------------------------
def _steps() -> list[dict]:
    """The live step list, created with a single step on first use."""
    import streamlit as st

    if STEPS_KEY not in st.session_state:
        st.session_state[UID_KEY] = 1
        st.session_state[STEPS_KEY] = [{"uid": 0, "name": DEFAULT_STEP}]
    return st.session_state[STEPS_KEY]


def _add_step() -> None:
    import streamlit as st

    steps = _steps()
    uid = st.session_state[UID_KEY]
    st.session_state[UID_KEY] = uid + 1
    steps.append({"uid": uid, "name": DEFAULT_STEP})


def _remove_step(uid: int) -> None:
    """Drop a step and the widget state that belonged to it.

    The keys have to go too: leaving them behind would hand a stale cutoff to
    the next step that happens to be given the same uid.
    """
    import streamlit as st

    st.session_state[STEPS_KEY] = [s for s in _steps() if s["uid"] != uid]
    prefix = _key_prefix(uid)
    for key in [k for k in st.session_state if str(k).startswith(prefix)]:
        del st.session_state[key]


def _key_prefix(uid: int) -> str:
    return f"chain:{uid}:"


# --------------------------------------------------------------------------
# widgets for one step
# --------------------------------------------------------------------------
def _clamp_state(key: str, lo, hi, cast) -> None:
    """Pull a stored widget value back inside bounds before the widget is made.

    Bounds move under the widget's feet: downsampling halves Nyquist, so a
    cutoff that was legal a rerun ago can now sit above the maximum, which
    Streamlit rejects outright.  Clamping first turns that crash into the
    obvious behaviour — the cutoff follows Nyquist down.
    """
    import streamlit as st

    if key not in st.session_state:
        return
    try:
        value = cast(st.session_state[key])
    except (TypeError, ValueError):
        return
    if lo is not None:
        value = max(cast(lo), value)
    if hi is not None:
        value = min(cast(hi), value)
    st.session_state[key] = value


def _param_widgets(name: str, prefix: str, nyquist: float) -> dict:
    """Build a sidebar widget per :class:`Param` and collect the chosen values.

    Keys carry the transform's name as well as the step's uid, so a step that
    is switched from Low-pass to Notch and back finds its old cutoff waiting
    rather than a value that belonged to a different function.

    A widget is given a starting ``value`` only the first time it is drawn.
    After that its state is the source of truth -- passing both is what makes
    Streamlit warn that the two disagree.
    """
    import streamlit as st

    params: dict[str, Any] = {}
    for p in get_transform(name).params:
        key = f"{prefix}{name}:{p.name}"
        seeded = key in st.session_state
        upper = nyquist if p.max_from == "nyquist" else p.max

        if p.kind == "bool":
            params[p.name] = st.checkbox(
                p.label, key=key, help=p.help or None,
                **({} if seeded else {"value": p.default}),
            )
        elif p.kind == "choice":
            options = list(p.options)
            if seeded and st.session_state[key] not in options:
                del st.session_state[key]
                seeded = False
            params[p.name] = st.selectbox(
                p.label, options, key=key, help=p.help or None,
                **({} if seeded else {"index": options.index(p.default)}),
            )
        elif p.kind == "int":
            lo = int(p.min) if p.min is not None else None
            hi = int(upper) if upper is not None else None
            _clamp_state(key, lo, hi, int)
            params[p.name] = int(st.number_input(
                p.label, min_value=lo, max_value=hi, step=int(p.step or 1),
                key=key, help=p.help or None,
                **({} if seeded else
                   {"value": int(p.default if hi is None else min(p.default, hi))}),
            ))
        else:  # float
            lo = float(p.min) if p.min is not None else None
            hi = float(upper) if upper is not None else None
            _clamp_state(key, lo, hi, float)
            params[p.name] = float(st.number_input(
                p.label, min_value=lo, max_value=hi, step=float(p.step or 1.0),
                key=key, help=p.help or None,
                **({} if seeded else
                   {"value": float(p.default if hi is None else min(p.default, hi))}),
            ))
    return params


# --------------------------------------------------------------------------
# the sidebar section app.py calls
# --------------------------------------------------------------------------
def chain_controls(df: pd.DataFrame) -> list[Stage]:
    """Render the Transform section and run the chain as it is built.

    Returns one :class:`Stage` per step, in order, ready to be turned into rows
    of the plot matrix.  Drawing and running are interleaved because each
    step's widgets need the frame that will actually reach it — see the module
    docstring.
    """
    import streamlit as st

    st.sidebar.header("Transform chain")
    st.sidebar.caption(
        "Each function takes the output of the one above it. Every step draws "
        "its own row of plots: input, output, and what the step removed."
    )

    steps = _steps()
    stages: list[Stage] = []
    current: pd.DataFrame | None = df
    source_label = df.attrs.get("source", "input") or "input"

    for i, step in enumerate(steps, start=1):
        prefix = _key_prefix(step["uid"])
        with st.sidebar.container(border=True):
            head, remove = st.columns([0.78, 0.22], vertical_alignment="bottom")
            options = list_transforms()
            name = head.selectbox(
                f"Step {i}", options,
                index=options.index(step["name"]) if step["name"] in options else 0,
                key=f"{prefix}name",
            )
            step["name"] = name
            remove.button(
                "✕", key=f"{prefix}drop", help="Remove this step",
                on_click=_remove_step, args=(step["uid"],),
                disabled=len(steps) == 1, width="stretch",
            )
            st.caption(get_transform(name).description)

            stage = Stage(index=i, uid=step["uid"], name=name, source=current,
                          source_label=source_label)

            if current is None:
                stage.error = "an earlier step failed, so this one never ran"
            elif current.attrs.get("domain") != "time":
                # An FFT or PSD hands on a spectrum; nothing downstream knows
                # how to filter one, so the chain stops here rather than
                # failing with a puzzling error from inside scipy.
                stage.error = (
                    f"step {i - 1} outputs a spectrum, which cannot be fed "
                    "back into a signal transform"
                )
            else:
                params = _param_widgets(name, prefix, nyquist=_nyquist(current))
                stage.params = params
                try:
                    stage.result = apply_transform(current, name, **params)
                    stage.result.attrs["transform"] = name
                except Exception as exc:  # noqa: BLE001 - surfaced in the row
                    stage.error = str(exc)

            if stage.error:
                st.warning(stage.error, icon="⚠️")

        stages.append(stage)
        current = stage.result
        source_label = f"after {stage.label}" if stage.ok else source_label

    st.sidebar.button(
        "➕ Add function", on_click=_add_step, width="stretch",
        help="Append a step to the chain — and a row to the plots.",
    )
    st.sidebar.caption(_chain_summary(df, stages))
    return stages


def _nyquist(df: pd.DataFrame) -> float:
    return float(df.attrs.get("sample_rate", 2.0)) / 2.0


def _chain_summary(df: pd.DataFrame, stages: list[Stage]) -> str:
    """One line reading the whole chain left to right."""
    parts = [df.attrs.get("source", "input") or "input"]
    parts += [s.name if s.ok else f"{s.name} ✕" for s in stages]
    return " → ".join(parts)


def chain_key(stages: list[Stage]) -> str:
    """Signature of the whole chain, for cache and axis-revision tokens."""
    return "|".join(f"{s.name}{sorted(s.params.items())}" for s in stages)


def final_result(stages: list[Stage]) -> pd.DataFrame | None:
    """Output of the last step that ran, or ``None`` if none did."""
    for stage in reversed(stages):
        if stage.ok:
            return stage.result
    return None
