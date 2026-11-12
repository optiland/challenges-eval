"""Convert an Optiland lens file (``save_optiland_file``) into a prescription.

Submissions are Optiland JSON files. The judge reads only the optical design
from them: surface radii, thicknesses, glasses, the stop and any physical
apertures. Fields, wavelengths, vignetting factors, ray aiming, apodization,
solves and pickups in the file are ignored; the judge sets them (RULES.md).

A surface without a physical aperture gets an automatic clear radius: the
largest real-ray height on that surface over the full pupil, at every
verification field and wavelength, plus ``AUTO_CLEAR_MARGIN``. Paraxial
semi-apertures are not used: real rays can be more than 25% higher at wide
field angles.

Lengths are millimetres. Optiland writes infinite values as the non-standard
JSON token ``Infinity``; the website stores them as the string "Infinity".
Both forms are accepted.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

AUTO_CLEAR_MARGIN = 1e-3          # relative margin on the real-ray footprint
FOOTPRINT_RINGS = 32              # pupil sampling for the footprint
FOOTPRINT_SPOKES = 128
FOOTPRINT_RIM_SPOKES = 720        # rim rays at normalized radius 1.0
GEOMETRY_TYPES = {"StandardGeometry": "sphere", "Plane": "plane"}
SUPPORTED_APERTURE_TYPES = {"float_by_stop_size", "EPD", "imageFNO"}


class ConversionError(ValueError):
    """The Optiland file cannot be a submission for these challenges."""


def loads(text: str) -> Any:
    """Parse Optiland JSON text, including the tokens Infinity and NaN."""
    return json.loads(text)


def is_optiland_file(data: Any) -> bool:
    """Return True if ``data`` looks like an Optiland lens file."""
    return isinstance(data, Mapping) and isinstance(data.get("surface_group"), Mapping)


def _number(value: Any, where: str) -> float:
    if isinstance(value, str) and value in {"Infinity", "-Infinity", "NaN"}:
        value = float(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConversionError(f"{where} must be a number.")
    return float(value)


def _zero(value: Any, where: str) -> None:
    if value is not None and _number(value, where) != 0.0:
        raise ConversionError(f"{where} must be zero: decentered or tilted surfaces are not allowed.")


def _material(raw: Any, where: str) -> str | dict[str, str]:
    if not isinstance(raw, Mapping):
        raise ConversionError(f"{where}: missing material.")
    kind = raw.get("type")
    if kind == "IdealMaterial":
        n = _number(raw.get("index"), f"{where} index")
        k = _number(raw.get("absorp", 0.0), f"{where} absorption")
        if n == 1.0 and k == 0.0:
            return "AIR"
        raise ConversionError(f"{where}: IdealMaterial is allowed only as air (index 1, no absorption). Use a catalog glass.")
    if kind == "Material":
        name = raw.get("name")
        catalog = raw.get("catalog") or raw.get("reference")
        if not isinstance(name, str) or not name.strip():
            raise ConversionError(f"{where}: the glass has no name.")
        if not isinstance(catalog, str) or not catalog.strip():
            raise ConversionError(
                f'{where}: glass "{name}" has no catalog. Create it as Material("{name}", catalog="SCHOTT") '
                "or with another catalog, so the name is not ambiguous.")
        return {"catalog": catalog.strip().upper(), "name": name.strip()}
    raise ConversionError(f"{where}: material type {kind!r} is not allowed. Use a catalog glass (Material) or air.")


def _surface(raw: Any, index: int) -> dict[str, Any]:
    where = f"Surface {index}"
    if not isinstance(raw, Mapping):
        raise ConversionError(f"{where} is not an object.")
    if raw.get("type") != "Surface":
        raise ConversionError(f"{where}: surface type {raw.get('type')!r} is not allowed.")
    geometry = raw.get("geometry")
    if not isinstance(geometry, Mapping) or geometry.get("type") not in GEOMETRY_TYPES:
        kind = geometry.get("type") if isinstance(geometry, Mapping) else None
        raise ConversionError(f"{where}: geometry {kind!r} is not allowed. Use spherical or plane surfaces.")
    cs = geometry.get("cs") or {}
    for key in ("x", "y", "rx", "ry", "rz"):
        _zero(cs.get(key), f"{where} coordinate {key}")
    if cs.get("reference_cs") is not None:
        raise ConversionError(f"{where}: a reference coordinate system is not allowed.")
    radius: float | None = None
    if GEOMETRY_TYPES[geometry["type"]] == "sphere":
        _zero(geometry.get("conic", 0.0), f"{where} conic")
        radius = _number(geometry.get("radius"), f"{where} radius")
        if math.isinf(radius):
            radius = None
        elif radius == 0.0 or math.isnan(radius):
            raise ConversionError(f"{where}: radius {radius} is not valid.")
    model = raw.get("interaction_model") or {}
    if model.get("type", "RefractiveReflectiveModel") != "RefractiveReflectiveModel":
        raise ConversionError(f"{where}: interaction model {model.get('type')!r} is not allowed.")
    if model.get("is_reflective"):
        raise ConversionError(f"{where}: mirrors are not allowed.")
    if model.get("coating") is not None or model.get("bsdf") is not None:
        raise ConversionError(f"{where}: coatings and scattering models are not allowed.")
    aperture = raw.get("aperture")
    clear: float | None = None
    if aperture is not None:
        if not isinstance(aperture, Mapping) or aperture.get("type") != "RadialAperture":
            raise ConversionError(f"{where}: only a RadialAperture is allowed as a physical aperture.")
        if _number(aperture.get("r_min", 0.0), f"{where} aperture r_min") != 0.0:
            raise ConversionError(f"{where}: an annular aperture (r_min > 0) is not allowed.")
        clear = _number(aperture.get("r_max"), f"{where} aperture r_max")
        if not (math.isfinite(clear) and clear > 0):
            raise ConversionError(f"{where}: aperture r_max must be a positive finite number.")
    return {
        "radius_mm": radius,
        "thickness_after_mm": _number(raw.get("thickness"), f"{where} thickness"),
        "material_after": _material(raw.get("material_post"), where),
        "clear_radius_mm": clear,
        "is_stop": bool(raw.get("is_stop")),
    }


def parse_optiland_file(data: Any) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Read the optical design from an Optiland lens file.

    Returns:
        (rows, aperture, notes). ``rows`` are the physical surfaces with
        ``clear_radius_mm`` None where the file has no physical aperture.
        ``aperture`` is {"type", "value"} from the file.

    Raises:
        ConversionError: For anything outside the challenge model.
    """
    if not is_optiland_file(data):
        raise ConversionError("This is not an Optiland lens file. Export your lens with "
                              "optiland.fileio.save_optiland_file(lens, 'my_lens.json').")
    raw_surfaces = data["surface_group"].get("surfaces")
    if not isinstance(raw_surfaces, list) or len(raw_surfaces) < 4:
        raise ConversionError("The lens must have an object surface, at least two lens surfaces and an image surface.")
    notes: list[str] = []
    obj = raw_surfaces[0]
    if not isinstance(obj, Mapping) or not math.isinf(_number(obj.get("thickness"), "Object thickness")):
        raise ConversionError("The object must be at infinity (object surface thickness = inf).")
    image = raw_surfaces[-1]
    image_geometry = image.get("geometry") if isinstance(image, Mapping) else None
    if not isinstance(image_geometry, Mapping) or image_geometry.get("type") not in GEOMETRY_TYPES:
        raise ConversionError("The image surface is not valid.")
    if image_geometry.get("type") == "StandardGeometry":
        r = _number(image_geometry.get("radius"), "Image radius")
        if math.isfinite(r):
            raise ConversionError("The sensor must be flat (image surface radius = inf).")
    for key in ("x", "y", "rx", "ry", "rz"):
        _zero((image_geometry.get("cs") or {}).get(key), f"Image surface coordinate {key}")
    rows = [_surface(raw, i) for i, raw in enumerate(raw_surfaces[1:-1])]
    stops = [i for i, row in enumerate(rows) if row["is_stop"]]
    if len(stops) != 1:
        raise ConversionError(f"The lens must have exactly one stop surface (found {len(stops)}).")
    aperture = data.get("aperture")
    if not isinstance(aperture, Mapping) or aperture.get("type") not in SUPPORTED_APERTURE_TYPES:
        kind = aperture.get("type") if isinstance(aperture, Mapping) else None
        raise ConversionError(f"Aperture type {kind!r} is not allowed. Use EPD, imageFNO or float_by_stop_size.")
    value = _number(aperture.get("value"), "Aperture value")
    if not (math.isfinite(value) and value > 0):
        raise ConversionError("The aperture value must be a positive number.")
    for key in ("fields", "wavelengths", "ray_tracer", "apodization", "solves", "pickups"):
        if data.get(key) not in (None, [], {}):
            notes.append(f"Ignored from the file: {key} (the judge sets these).")
    return rows, {"type": aperture["type"], "value": value}, notes


def _canonical(rows, stop_index, stop_radius, clear_radii, name):
    surfaces = [{"radius_mm": r["radius_mm"], "thickness_after_mm": r["thickness_after_mm"],
                 "material_after": r["material_after"], "clear_radius_mm": float(c)}
                for r, c in zip(rows, clear_radii)]
    out = {"surfaces": surfaces, "stop_surface": stop_index, "stop_radius_mm": float(stop_radius)}
    if isinstance(name, str) and name:
        out["name"] = name
    return out


def _stop_radius(rows, stop_index, aperture, fields_deg, wavelengths_um):
    if aperture["type"] == "float_by_stop_size":
        return aperture["value"] / 2.0
    from prescription import build_optic

    # Temporary optic: tiny apertures pass validation; the paraxial marginal
    # ray height at the stop gives the stop radius for EPD or image F/#.
    trial = _canonical(rows, stop_index, 1e-6, [1e-6] * len(rows), None)
    optic = build_optic(trial, fields_deg, wavelengths_um)
    optic.set_aperture(aperture_type=aperture["type"], value=aperture["value"])
    ya, _ = optic.paraxial.marginal_ray()
    radius = abs(float(np.ravel(np.asarray(ya))[stop_index + 1]))
    if not (math.isfinite(radius) and radius > 0):
        raise ConversionError("The stop radius cannot be calculated from the aperture definition.")
    return radius


def real_ray_footprint(prescription, fields_deg, verification_step_deg, wavelengths_um, free_surfaces):
    """Largest real-ray height on each surface over the verification grid.

    Surfaces in ``free_surfaces`` have no aperture during this trace. Rays that
    are lost anyway are ignored here; the evaluator reports them later.
    """
    from challenge_evaluator import pupil_quadrature
    from prescription import build_optic

    optic = build_optic(prescription, fields_deg, wavelengths_um)
    for i in free_surfaces:
        optic.surfaces[i + 1].aperture = None
    px, py, _ = pupil_quadrature(FOOTPRINT_RINGS, FOOTPRINT_SPOKES)
    phi = 2 * np.pi * np.arange(FOOTPRINT_RIM_SPOKES) / FOOTPRINT_RIM_SPOKES
    px = np.r_[px, 0.0, np.cos(phi)]
    py = np.r_[py, 0.0, np.sin(phi)]
    max_field = fields_deg[-1]
    steps = int(round(max_field / verification_step_deg))
    footprint = np.zeros(len(prescription["surfaces"]))
    for angle in np.linspace(0.0, max_field, steps + 1):
        for wavelength in wavelengths_um:
            optic.ray_tracer.trace_generic(0.0, angle / max_field, px, py, wavelength, record=True)
            for i in range(len(footprint)):
                s = optic.surfaces[i + 1]
                r = np.hypot(np.asarray(s.x, dtype=float).ravel(), np.asarray(s.y, dtype=float).ravel())
                ok = np.isfinite(r) & (np.asarray(s.intensity, dtype=float).ravel() > 0)
                if np.any(ok):
                    footprint[i] = max(footprint[i], float(np.max(r[ok])))
    return footprint


def prescription_from_optiland(data: Any, fields_deg: Sequence[float], verification_step_deg: float,
                               wavelengths_um: Sequence[float]) -> tuple[dict[str, Any], list[str]]:
    """Convert an Optiland lens file into the canonical prescription.

    Args:
        data: Parsed Optiland lens file.
        fields_deg: Scoring fields of the challenge (the last is the maximum).
        verification_step_deg: Verification field step of the challenge.
        wavelengths_um: Judge wavelengths.

    Returns:
        (prescription, notes). Notes list each automatic clear radius and
        each ignored setting.

    Raises:
        ConversionError: For anything outside the challenge model.
    """
    rows, aperture, notes = parse_optiland_file(data)
    stop_index = next(i for i, row in enumerate(rows) if row["is_stop"])
    try:
        stop_radius = _stop_radius(rows, stop_index, aperture, fields_deg, wavelengths_um)
    except ConversionError:
        raise
    except (ValueError, ArithmeticError) as exc:
        raise ConversionError(f"The lens cannot be built: {exc}") from exc
    declared = [row["clear_radius_mm"] for row in rows]
    if declared[stop_index] is not None and declared[stop_index] + 1e-9 < stop_radius:
        notes.append(f"Stop surface {stop_index}: its aperture ({declared[stop_index]:.6g} mm) is smaller than the "
                     f"stop radius from the aperture definition ({stop_radius:.6g} mm); the stop radius is used.")
    free = [i for i, c in enumerate(declared) if c is None and i != stop_index]
    trial_clear = [stop_radius if i == stop_index else (c if c is not None else 1e-6)
                   for i, c in enumerate(declared)]
    trial = _canonical(rows, stop_index, stop_radius, trial_clear, data.get("name"))
    try:
        footprint = real_ray_footprint(trial, list(fields_deg), verification_step_deg, wavelengths_um, free)
    except (ValueError, ArithmeticError) as exc:
        raise ConversionError(f"The lens cannot be traced: {exc}") from exc
    clear = list(trial_clear)
    for i in free:
        if footprint[i] <= 0:
            raise ConversionError(f"Surface {i}: no ray reaches this surface.")
        clear[i] = footprint[i] * (1 + AUTO_CLEAR_MARGIN)
        notes.append(f"Surface {i}: automatic clear radius {clear[i]:.6f} mm (real-ray footprint + 0.1%).")
    if declared[stop_index] is not None:
        clear[stop_index] = max(declared[stop_index], stop_radius)
    return _canonical(rows, stop_index, stop_radius, clear, data.get("name")), notes
