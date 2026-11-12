"""Numeric prescriptions of centered spherical lenses for the challenges.

Lengths are millimetres and wavelengths are micrometres.  A JSON prescription
contains physical surfaces only; the infinite object and flat image are added
by ``build_optic``.  A null radius denotes a plane.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

import numpy as np

WAVELENGTHS_UM = (0.4861327, 0.5875618, 0.6562725)
PRIMARY_UM = 0.5875618
GEOMETRY_TOL_MM = 1e-9


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number.")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name} must be finite" + (" and positive." if positive else "."))
    return result


def _material_key(value: Any) -> tuple[str, str] | str:
    if value == "AIR":
        return "AIR"
    if not isinstance(value, Mapping) or set(value) != {"catalog", "name"}:
        raise ValueError("material_after must be 'AIR' or {'catalog': str, 'name': str}.")
    if any(not isinstance(value[k], str) or not value[k].strip() for k in value):
        raise ValueError("Glass catalog and name must be non-empty strings.")
    return (value["catalog"].strip().casefold(), value["name"].strip().casefold())


def _parse(spec: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int, float]:
    if not isinstance(spec, Mapping):
        raise ValueError("A prescription must be a JSON object.")
    required = {"surfaces", "stop_surface", "stop_radius_mm"}
    if not required <= set(spec) or set(spec) - required - {"name"}:
        raise ValueError("Top-level keys must be surfaces, stop_surface, stop_radius_mm and optional name.")
    if "name" in spec and not isinstance(spec["name"], str):
        raise ValueError("name must be a string.")
    entries = spec["surfaces"]
    if not isinstance(entries, list) or len(entries) < 2:
        raise ValueError("surfaces must contain at least two physical surfaces.")
    stop = spec["stop_surface"]
    if isinstance(stop, bool) or not isinstance(stop, int) or not 0 <= stop < len(entries):
        raise ValueError("stop_surface must index one physical surface (zero based).")
    stop_radius = _number(spec["stop_radius_mm"], "stop_radius_mm", positive=True)
    keys = {"radius_mm", "thickness_after_mm", "material_after", "clear_radius_mm"}
    rows: list[dict[str, Any]] = []
    z = 0.0
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or set(entry) != keys:
            raise ValueError(f"Surface {index}: required keys are {sorted(keys)}.")
        radius = entry["radius_mm"]
        if radius is not None:
            radius = _number(radius, f"Surface {index} radius_mm")
            if radius == 0:
                raise ValueError(f"Surface {index}: radius zero is not valid; use null for a plane.")
        thickness = _number(entry["thickness_after_mm"], f"Surface {index} thickness_after_mm")
        if thickness < 0:
            raise ValueError(f"Surface {index}: negative axial thickness is not allowed.")
        clear = _number(entry["clear_radius_mm"], f"Surface {index} clear_radius_mm", positive=True)
        rows.append({**entry, "radius_mm": radius, "thickness_after_mm": thickness,
                     "clear_radius_mm": clear, "material_key": _material_key(entry["material_after"]),
                     "z_mm": z})
        z += thickness
        if not math.isfinite(z):
            raise ValueError("The accumulated track length must be finite.")
    return rows, stop, stop_radius


def spherical_sag(radius_mm: float | None, height_mm: float) -> float:
    """Return the vertex-connected spherical sag with the signed-radius convention.

    Args:
        radius_mm: Signed radius of curvature, or None for a plane.
        height_mm: Non-negative radial coordinate.

    Returns:
        Axial sag in millimetres.

    Raises:
        ValueError: If the radius is zero or the cap is outside its real domain.
    """
    if radius_mm is None:
        return 0.0
    if radius_mm == 0 or abs(height_mm) >= abs(radius_mm):
        raise ValueError("A spherical cap must have height strictly smaller than |radius|.")
    ratio = height_mm / radius_mm
    return (height_mm * ratio) / (1.0 + math.sqrt(1.0 - ratio * ratio))


def _mechanical_radii(rows: list[dict[str, Any]]) -> list[float]:
    """Extend each glass/cemented group to its largest declared face radius."""
    radii = [r["clear_radius_mm"] for r in rows]
    i = 0
    while i < len(rows) - 1:
        if rows[i]["material_key"] == "AIR":
            i += 1
            continue
        first = i
        while i < len(rows) - 1 and rows[i]["material_key"] != "AIR":
            i += 1
        group_radius = max(radii[first:i + 1])
        radii[first:i + 1] = [group_radius] * (i + 1 - first)
    return radii


def validate_prescription(
    spec: Mapping[str, Any], *, min_center_mm: float = 2.0,
    min_edge_mm: float = 1.0, tolerance_mm: float = GEOMETRY_TOL_MM,
) -> list[str]:
    """Validate schema, spherical caps, lens edges, surface order and stop placement.

    An element is one non-air axial material interval.  A cemented doublet
    therefore has two elements and three interfaces.  A glass or cemented
    group's mechanical edge radius is the largest clear radius on its faces.
    The submitted clear radii still determine ray clipping individually.

    For centered spherical/plane graph surfaces, the separation on a common
    radial disk is monotonic; checking its axis and edge checks its minimum.
    This is a cap/blank model, without mounts, bevels or cement-layer thickness.

    Args:
        spec: Plain JSON-compatible prescription.
        min_center_mm: Minimum glass center thickness.
        min_edge_mm: Minimum glass edge thickness.
        tolerance_mm: Numerical comparison allowance, not a design tolerance.

    Returns:
        Human-readable violation messages; an empty list means these checks pass.
    """
    try:
        rows, stop, stop_radius = _parse(spec)
    except (ValueError, TypeError) as exc:
        return [str(exc)]
    errors: list[str] = []
    if rows[-1]["material_key"] != "AIR":
        errors.append("The image space after the last physical surface must be AIR.")
    if rows[-1]["thickness_after_mm"] <= 0:
        errors.append("The sensor must lie a positive axial distance after the last physical surface.")
    if stop_radius > rows[stop]["clear_radius_mm"] + tolerance_mm:
        errors.append("The stop radius exceeds its surface clear radius.")
    mechanical = _mechanical_radii(rows)
    cap_ok = []
    for i, (row, r_edge) in enumerate(zip(rows, mechanical)):
        okay = row["radius_mm"] is None or r_edge < abs(row["radius_mm"])
        cap_ok.append(okay)
        if not okay:
            errors.append(f"Surface {i}: mechanical radius must be smaller than |spherical radius|.")
    previous_material: tuple[str, str] | str = "AIR"
    refracting_indices = []
    for i, row in enumerate(rows):
        current = row["material_key"]
        if previous_material == current:
            if not (current == "AIR" and i == stop and row["radius_mm"] is None):
                errors.append(f"Surface {i}: a same-material interface is allowed only for a plane AIR-to-AIR stop.")
        else:
            refracting_indices.append(i)
        previous_material = current
    if not refracting_indices:
        errors.append("At least one glass element is required.")
    elif not (rows[refracting_indices[0]]["z_mm"] - tolerance_mm <= rows[stop]["z_mm"]
              <= rows[refracting_indices[-1]]["z_mm"] + tolerance_mm):
        errors.append("The stop must lie between the first and last refracting interface, inclusive.")
    for i in range(len(rows) - 1):
        a, b = rows[i:i + 2]
        glass = a["material_key"] != "AIR"
        center = a["thickness_after_mm"]
        if glass and center < min_center_mm - tolerance_mm:
            errors.append(f"Element after surface {i}: center thickness {center:.9g} mm is below {min_center_mm:g} mm.")
        if not (cap_ok[i] and cap_ok[i + 1]):
            continue
        r_edge = mechanical[i] if glass else min(mechanical[i], mechanical[i + 1])
        edge = center + spherical_sag(b["radius_mm"], r_edge) - spherical_sag(a["radius_mm"], r_edge)
        if glass and edge < min_edge_mm - tolerance_mm:
            errors.append(f"Element after surface {i}: edge thickness {edge:.9g} mm is below {min_edge_mm:g} mm.")
        if not glass and min(center, edge) < -tolerance_mm:
            errors.append(f"Air interval after surface {i}: neighboring spherical caps intersect (minimum gap {min(center, edge):.9g} mm).")
    # An intervening smaller-radius element or stop must not conceal an
    # overlap of larger glass blanks outside that intervening aperture.  The
    # adjacent checks alone cannot establish ordering on those outer annuli.
    for i in range(len(rows) - 2):
        for j in range(i + 2, len(rows)):
            if not (cap_ok[i] and cap_ok[j]):
                continue
            shared_radius = min(mechanical[i], mechanical[j])
            center = rows[j]["z_mm"] - rows[i]["z_mm"]
            edge = center + spherical_sag(rows[j]["radius_mm"], shared_radius) - spherical_sag(rows[i]["radius_mm"], shared_radius)
            if min(center, edge) < -tolerance_mm:
                errors.append(f"Nonadjacent surfaces {i} and {j}: spherical caps intersect over their shared mechanical disk (minimum gap {min(center, edge):.9g} mm).")
    # Include the flat image plane in the nonintersection test.  Its modeled
    # active radius need not be specified; all rays are checked separately.
    if cap_ok[-1]:
        sensor_gap = rows[-1]["thickness_after_mm"] - spherical_sag(rows[-1]["radius_mm"], mechanical[-1])
        if sensor_gap < -tolerance_mm:
            errors.append("The last spherical cap intersects the flat sensor plane.")
    return errors


def prescription_facts(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Return geometric facts for a structurally well-formed prescription.

    Args:
        spec: Plain JSON-compatible prescription.

    Returns:
        Element intervals, track, sensor clearance, vertex positions and radii.
    """
    rows, stop, stop_radius = _parse(spec)
    mechanical = _mechanical_radii(rows)
    elements = []
    for i, row in enumerate(rows[:-1]):
        if row["material_key"] == "AIR":
            continue
        edge = (row["thickness_after_mm"] + spherical_sag(rows[i + 1]["radius_mm"], mechanical[i])
                - spherical_sag(row["radius_mm"], mechanical[i]))
        glass = catalog_material(row["material_after"])
        nf, nd, nc = np.asarray(glass.n(np.asarray(WAVELENGTHS_UM)), dtype=float).reshape(-1)
        if not math.isfinite(float(nf - nc)) or nf == nc:
            raise ValueError(f"Element after surface {i}: a finite nonzero F-to-C dispersion is required.")
        c1 = 0.0 if row["radius_mm"] is None else 1.0 / row["radius_mm"]
        c2 = 0.0 if rows[i + 1]["radius_mm"] is None else 1.0 / rows[i + 1]["radius_mm"]
        power = (nd - 1) * (c1 - c2 + (nd - 1) * row["thickness_after_mm"] * c1 * c2 / nd)
        elements.append({"front_surface": i, "back_surface": i + 1,
                         "center_thickness_mm": row["thickness_after_mm"],
                         "edge_thickness_mm": edge, "mechanical_radius_mm": mechanical[i],
                         "material": row["material_after"],
                         "catalog_file": glass.material_data["filename"],
                         "refractive_indices_FdC": [float(nf), float(nd), float(nc)],
                         "abbe_number": float((nd - 1) / (nf - nc)),
                         "isolated_power_per_mm": float(power)})
    previous: tuple[str, str] | str = "AIR"
    refracting = []
    for i, row in enumerate(rows):
        if previous != row["material_key"]:
            refracting.append(i)
        previous = row["material_key"]
    sensor_z = sum(r["thickness_after_mm"] for r in rows)
    bfd = sensor_z - rows[refracting[-1]]["z_mm"] if refracting else sensor_z
    return {"element_count": len(elements), "elements": elements,
            "total_track_mm": sensor_z - rows[refracting[0]]["z_mm"] if refracting else sensor_z,
            "sensor_distance_from_last_interface_mm": bfd, "bfd_mm": bfd,
            "minimum_center_thickness_mm": min((e["center_thickness_mm"] for e in elements), default=0.0),
            "minimum_edge_thickness_mm": min((e["edge_thickness_mm"] for e in elements), default=0.0),
            "stop_vertex_mm": rows[stop]["z_mm"], "stop_radius_mm": stop_radius,
            "vertex_positions_mm": [r["z_mm"] for r in rows],
            "mechanical_radii_mm": mechanical}


def catalog_material(material_spec: Mapping[str, str], wavelengths_um: Sequence[float] = WAVELENGTHS_UM):
    """Resolve a bundled catalog glass strictly and verify its spectral domain.

    Args:
        material_spec: Exact catalog and glass name.
        wavelengths_um: Wavelengths that the evaluator will trace.

    Returns:
        A new ordinary Optiland Material object.

    Raises:
        ValueError: For non-glass records, unsupported wavelengths or invalid n.
    """
    from optiland.materials import Material
    from optiland.materials.material_spec import MatchPolicy

    _material_key(material_spec)
    glass = Material(material_spec["name"], catalog=material_spec["catalog"],
                     match_policy=MatchPolicy.STRICT, bounds="raise")
    metadata = glass.material_data
    if str(metadata.get("group", "")).casefold() != "glass":
        raise ValueError(f"{material_spec}: the resolved catalog record is not in the glass group.")
    low, high = float(metadata["min_wavelength"]), float(metadata["max_wavelength"])
    if min(wavelengths_um) < low or max(wavelengths_um) > high:
        raise ValueError(f"{material_spec}: catalog range [{low}, {high}] um does not cover all evaluation wavelengths.")
    raw_n = np.asarray(glass.n(np.asarray(wavelengths_um, dtype=float)))
    if np.iscomplexobj(raw_n):
        raise ValueError(f"{material_spec}: complex refractive-index data are not supported by this refractive benchmark.")
    n = np.asarray(raw_n, dtype=float)
    if not np.all(np.isfinite(n)) or not np.all(n > 1):
        raise ValueError(f"{material_spec}: finite real glass refractive indices above 1 are required.")
    return glass


def build_optic(spec: Mapping[str, Any], fields_deg: Sequence[float],
                wavelengths_um: Sequence[float] = WAVELENGTHS_UM):
    """Build a fresh ordinary Optiland lens with canonical evaluation settings.

    The prescription fixes the actual stop radius; EPD and F/# are measured
    afterwards, not used to resize the pupil.  Wavelengths share one physical
    stop and one flat sensor.  No focus solve, apodization, custom interaction,
    coating, field vignetting factor, decenter, tilt, mirror or asphere is added.
    Material absorption, if present in the bundled glass, remains physical.

    Args:
        spec: Plain JSON-compatible prescription.
        fields_deg: Non-negative semi-field angles in degrees.
        wavelengths_um: Evaluator-owned wavelengths, including exactly 0.5875618 um.

    Returns:
        A fresh Optiland Optic.  The physical stop index is ``stop_surface + 1``.

    Raises:
        ValueError: If schema, physical caps, fields, wavelengths or glasses fail.
    """
    from optiland.optic import Optic
    from optiland.physical_apertures import RadialAperture

    failures = validate_prescription(spec, min_center_mm=0.0, min_edge_mm=0.0)
    if failures:
        raise ValueError("; ".join(failures))
    rows, stop, stop_radius = _parse(spec)
    fields = tuple(_number(x, "field angle") for x in fields_deg)
    wavelengths = tuple(_number(x, "wavelength", positive=True) for x in wavelengths_um)
    if not fields or any(x < 0 or x >= 90 for x in fields):
        raise ValueError("fields_deg must contain non-negative angles below 90 degrees.")
    if not wavelengths or PRIMARY_UM not in wavelengths or len(set(wavelengths)) != len(wavelengths):
        raise ValueError("Evaluation wavelengths must be distinct and include 0.5875618 um.")
    lens = Optic(name=spec.get("name", "Competition prescription"))
    lens.surfaces.add(index=0, thickness=float("inf"))
    cache: dict[tuple[str, str], Any] = {}
    for i, row in enumerate(rows):
        key = row["material_key"]
        if key == "AIR":
            material: Any = "air"
        else:
            if key not in cache:
                cache[key] = catalog_material(row["material_after"], wavelengths)
            material = cache[key]
        aperture_radius = stop_radius if i == stop else row["clear_radius_mm"]
        lens.surfaces.add(index=i + 1,
                          radius=float("inf") if row["radius_mm"] is None else row["radius_mm"],
                          thickness=row["thickness_after_mm"], material=material,
                          is_stop=i == stop, aperture=RadialAperture(r_max=aperture_radius))
        lens.surfaces[i + 1].semi_aperture = row["clear_radius_mm"]
    lens.surfaces.add(index=len(rows) + 1, thickness=0.0)
    lens.set_aperture(aperture_type="float_by_stop_size", value=2 * stop_radius)
    lens.fields.set_type("angle")
    for angle in fields:
        lens.fields.add(y=angle, x=0.0, vx=0.0, vy=0.0, weight=1.0 / len(fields))
    for wavelength in wavelengths:
        lens.wavelengths.add(value=wavelength, is_primary=wavelength == PRIMARY_UM,
                             weight=1.0 / len(wavelengths))
    lens.ray_tracer.set_aiming(mode="robust", max_iter=50, tol=1e-9)
    return lens
