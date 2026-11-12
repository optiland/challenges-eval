"""Deterministic reference evaluator for a proposed v2 Optiland starter pack.

This is a reviewable proposal, not the evaluator used by the live website.
The public input is a numeric prescription. Optimizer settings are never read.
All lengths are millimetres, wavelengths micrometres, and field angles degrees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

from polychromatic_mtf import polychromatic_fft_mtf
from prescription import build_optic, prescription_facts, validate_prescription

EVALUATOR_VERSION = "2.0.0-proposal"
OPTILAND_COMMIT = "61f096bbf038b29a19681aabda5a061bf839b40c"
WAVELENGTHS_UM = (0.4861327, 0.5875618, 0.6562725)
PRIMARY_UM = WAVELENGTHS_UM[1]
PUPIL_RINGS = 16
PUPIL_SPOKES = 64
RIM_SPOKES = 256
RIM_RADIUS = 1.0 - 1e-6
AIM_RESIDUAL_MM = 1e-7
FORWARD_TOL_MM = 1e-8
RMS_CONVERGENCE_REL = 1e-3
RMS_CONVERGENCE_ABS_MM = 1e-8
MTF_CONVERGENCE_ABS = 0.005


@dataclass(frozen=True)
class Challenge:
    """Frozen specification for one proposed challenge."""

    fields_deg: tuple[float, ...]
    verification_step_deg: float
    efl_mm: float
    efl_relative_tolerance: float
    f_number: float
    f_number_relative_tolerance: float
    elements_min: int
    elements_max: int
    bfd_min_mm: float
    track_max_mm: float | None
    distortion_max: float
    rms_scale_mm: float | None


CHALLENGES = {
    "rms": Challenge((0, 7, 10, 12, 14), 1, 50, .01, 4, .02, 3, 6, 10, 80, .02, .025),
    "doublet": Challenge((0, 1.5, 3), .25, 100, .01, 8, .02, 2, 2, 60, None, .005, .020),
    "wide_angle": Challenge((0, 10, 20, 30), 1, 24, .02, 4, .05, 5, 8, 12, 80, .02, None),
}


def pupil_quadrature(rings: int = PUPIL_RINGS, spokes: int = PUPIL_SPOKES):
    """Return fixed area quadrature on the normalized physical stop disk.

    Gauss-Legendre nodes integrate in rho squared; azimuth is uniform. These
    weights define the geometric benchmark, not entrance-pupil power throughput.
    """
    nodes, weights = np.polynomial.legendre.leggauss(rings)
    rho = np.sqrt((nodes + 1) / 2)
    phi = 2 * np.pi * np.arange(spokes) / spokes
    px = (rho[:, None] * np.cos(phi)).ravel()
    py = (rho[:, None] * np.sin(phi)).ravel()
    q = np.repeat(weights / (2 * spokes), spokes)
    return px, py, q


def polychromatic_rms(xy: np.ndarray, pupil_weights: np.ndarray) -> dict:
    """Compute a single broadband centroid and RMS radius at one field.

    Args:
        xy: Ray intersections shaped (wavelength, pupil sample, x/y), in mm.
        pupil_weights: Nonnegative weights for the complete launched pupil.

    Returns:
        Broadband RMS, common centroid, and monochromatic centroid diagnostics.

    Raises:
        ValueError: If any ray or weight is missing or nonfinite.
    """
    data = np.asarray(xy, dtype=np.float64)
    q = np.asarray(pupil_weights, dtype=np.float64)
    if data.ndim != 3 or data.shape[2] != 2 or q.shape != (data.shape[1],):
        raise ValueError("Expected xy[wavelength, ray, 2] and one weight per ray.")
    if not np.all(np.isfinite(data)) or not np.all(np.isfinite(q)):
        raise ValueError("Missing or nonfinite rays must not be omitted from RMS.")
    if np.any(q < 0) or q.sum() <= 0:
        raise ValueError("Pupil weights must be nonnegative with positive sum.")
    q = q / q.sum()
    centers = np.sum(data * q[None, :, None], axis=1)
    common = centers.mean(axis=0)  # equal spectral weights
    squared = np.sum((data - common[None, None, :]) ** 2, axis=2)
    variance = np.mean(np.sum(squared * q[None, :], axis=1))
    if not np.isfinite(variance):
        raise ValueError("The computed spot variance is nonfinite.")
    within = np.sum((data - centers[:, None, :]) ** 2, axis=2)
    return {
        "rms_mm": float(np.sqrt(max(0.0, variance))),
        "centroid_xy_mm": common.tolist(),
        "monochromatic_centroid_xy_mm": centers.tolist(),
        "monochromatic_rms_about_own_centroid_mm": np.sqrt(within @ q).tolist(),
        "centroid_lateral_colour_FC_mm": float(np.linalg.norm(centers[0] - centers[-1])),
    }


DIGEST_SUFFIXES = {".py", ".csv", ".yml", ".yaml", ".npy"}
BINARY_SUFFIXES = {".npy"}


def tree_digest(root: Path) -> tuple[str, int]:
    """Return a platform-independent SHA-256 digest of an installed source tree.

    The digest must be equal on Linux, macOS and Windows for the same commit.
    Two platform effects are removed:

    * Order: files are sorted by their POSIX relative path. ``Path`` ordering
      ignores case on Windows and cannot be used.
    * Line endings: Git for Windows (``core.autocrlf=true``) checks text files
      out with CRLF. Text files are hashed with CRLF converted to LF. Binary
      files (``.npy``) are hashed unchanged.

    Args:
        root: Package directory to hash.

    Returns:
        Hex digest and number of hashed files.
    """
    paths = [p for p in root.rglob("*") if p.is_file()
             and p.suffix in DIGEST_SUFFIXES and "__pycache__" not in p.parts]
    relative = sorted((PurePosixPath(p.relative_to(root).as_posix()), p) for p in paths)
    digest = hashlib.sha256()
    for name, path in relative:
        data = path.read_bytes()
        if path.suffix not in BINARY_SUFFIXES:
            data = data.replace(b"\r\n", b"\n")
        digest.update(str(name).encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest(), len(relative)


def _engine_digest() -> tuple[str, int]:
    import optiland

    return tree_digest(Path(optiland.__file__).resolve().parent)


@lru_cache(maxsize=1)
def engine_provenance() -> dict:
    """Verify the frozen engine/catalog bytes and record numerical dependencies."""
    lock = json.loads(Path(__file__).with_name("engine_lock.json").read_text())
    digest, count = _engine_digest()
    versions = {name: metadata.version(name) for name in ("optiland", "numpy", "scipy")}
    mismatch = []
    if digest != lock["source_catalog_sha256"]:
        mismatch.append("Optiland source/catalog bytes differ from the published engine lock.")
    for name in ("numpy", "scipy"):
        if versions[name] != lock["versions"][name]:
            mismatch.append(f"{name} version differs from the published engine lock.")
    return {"expected_commit": OPTILAND_COMMIT, "source_catalog_sha256": digest,
            "hashed_files": count, "versions": versions, "mismatch": mismatch}


def _trace_bundle(optic, angle_deg, maximum_field_deg, px, py, stop_radius_mm):
    """Trace all samples and retain failures rather than dropping their rays."""
    optic.ray_tracer.trace_generic(
        0.0, angle_deg / maximum_field_deg, px, py, optic._judge_wavelength, record=True
    )
    return _validate_recorded_bundle(optic, px, py, stop_radius_mm)


def _validate_recorded_bundle(optic, px, py, stop_radius_mm):
    """Validate current snapshots before another trace can overwrite them."""
    px, py = np.asarray(px).reshape(-1), np.asarray(py).reshape(-1)
    count = len(px)
    valid = np.ones(count, dtype=bool)
    backward = np.zeros(count, dtype=bool)
    wrong_cap = np.zeros(count, dtype=bool)
    previous_xyz = None
    previous_k = None
    for surface in optic.surfaces.surfaces[1:]:  # object at infinity is not a hit
        arrays = [np.asarray(getattr(surface, a), dtype=float).reshape(-1)
                  for a in ("x", "y", "z", "L", "M", "N", "intensity")]
        if any(len(a) != count for a in arrays):
            raise ValueError("The tracer changed the number of launched samples.")
        hit = np.column_stack(arrays[:3])
        direction = np.column_stack(arrays[3:6])
        valid &= np.all(np.isfinite(np.column_stack(arrays)), axis=1) & (arrays[6] > 0)
        # A finite intersection on a sphere's far hemisphere is not a hit on
        # the vertex-connected optical cap declared by the prescription.
        radius = float(np.asarray(getattr(surface.geometry, "radius", np.inf)).item())
        vertex = float(np.asarray(surface.geometry.cs.z).item())
        if math.isfinite(radius):
            r2 = arrays[0] ** 2 + arrays[1] ** 2
            inside = r2 < radius * radius
            expected_sag = r2 / (radius * (1 + np.sqrt(np.maximum(0, 1 - r2 / (radius * radius)))))
            wrong_cap |= ~inside | (abs(arrays[2] - vertex - expected_sag) > AIM_RESIDUAL_MM)
        else:
            wrong_cap |= abs(arrays[2] - vertex) > AIM_RESIDUAL_MM
        if previous_xyz is not None:
            travel = np.sum((hit - previous_xyz) * previous_k, axis=1)
            backward |= travel < -FORWARD_TOL_MM
        previous_xyz, previous_k = hit, direction
    stop = optic.surfaces[optic.surfaces.stop_index]
    residual = np.hypot(np.asarray(stop.x).reshape(-1) - stop_radius_mm * px,
                        np.asarray(stop.y).reshape(-1) - stop_radius_mm * py)
    valid &= np.isfinite(residual) & (residual <= AIM_RESIDUAL_MM) & ~backward & ~wrong_cap
    aiming = getattr(optic.ray_tracer.ray_generator.aimer, "last_report", None)
    if aiming is not None and not aiming.converged:
        valid[:] = False
    image = optic.image_surface
    xy = np.column_stack((np.asarray(image.x).reshape(-1), np.asarray(image.y).reshape(-1)))
    valid &= np.all(np.isfinite(xy), axis=1)
    return xy, valid, {
        "launched_rays": count,
        "valid_rays": int(valid.sum()),
        "failed_rays": int((~valid).sum()),
        "backward_rays": int(backward.sum()),
        "wrong_spherical_cap_rays": int(wrong_cap.sum()),
        "maximum_stop_aim_residual_mm": float(np.max(residual)) if np.all(np.isfinite(residual)) else None,
    }


def _paraxial_focus_offsets(optic) -> list[float]:
    values = []
    for wavelength in WAVELENGTHS_UM:
        # Axial collimated ray, launched 1 mm before the first vertex. This
        # yields rear focus offsets from ONE fixed image plane; EFL differences
        # would be incorrect when principal planes move with wavelength.
        y, u = optic.paraxial.trace_generic(1.0, 0.0, -1.0, wavelength)
        values.append(float(np.asarray(-y[-1] / u[-1]).item()))
    if not np.all(np.isfinite(values)):
        raise ValueError("Nonfinite paraxial focus position.")
    return values


def _constraint(report, label, value, minimum=None, maximum=None, tolerance=1e-9):
    finite = math.isfinite(value)
    valid = finite
    if minimum is not None:
        valid &= value >= minimum - tolerance
    if maximum is not None:
        valid &= value <= maximum + tolerance
    report["constraints"].append({"name": label, "value": value if finite else None, "minimum": minimum,
                                   "maximum": maximum, "passed": bool(valid)})
    if not valid:
        report["violations"].append(f"{label}: {value:g}; required [{minimum}, {maximum}].")


def evaluate_design(prescription: dict, challenge: str = "rms") -> dict[str, Any]:
    """Rebuild, validate, and score a proposed challenge submission.

    A result is eligible only if all geometric, optical and convergence checks
    pass. Invalid designs return score=None and explicit violations. This
    function never optimizes, changes the submitted sensor plane, or publishes.
    """
    if challenge not in CHALLENGES:
        raise ValueError(f"challenge must be one of {tuple(CHALLENGES)}")
    import optiland.backend as be

    be.set_backend("numpy")
    spec = CHALLENGES[challenge]
    report: dict[str, Any] = {
        "evaluator_version": EVALUATOR_VERSION, "challenge": challenge,
        "eligible": False, "status": "invalid", "score": None, "violations": [], "constraints": [],
        "settings": {
            "wavelengths_um": list(WAVELENGTHS_UM), "spectral_weights": [1 / 3] * 3,
            "fields_deg": list(spec.fields_deg), "field_weights": [1 / len(spec.fields_deg)] * len(spec.fields_deg),
            "pupil_rings": PUPIL_RINGS, "pupil_spokes": PUPIL_SPOKES,
            "verification_rim_spokes": RIM_SPOKES, "verification_rim_radius": RIM_RADIUS,
            "stop_aim_residual_tolerance_mm": AIM_RESIDUAL_MM,
            "vignetting_policy": "No blocked, missing, TIR, backward, or mis-aimed test rays",
            "focus_policy": "One submitted flat sensor; no refocusing",
        },
    }
    try:
        report["engine"] = engine_provenance()
        if report["engine"]["mismatch"]:
            report["status"] = "environment_mismatch"
            report["violations"].extend(report["engine"]["mismatch"])
            return report
        geometry_failures = validate_prescription(prescription)
        if geometry_failures:
            report["violations"].extend(geometry_failures)
            return report
        geometry = prescription_facts(prescription)
        report["geometry"] = geometry
        optic = build_optic(prescription, spec.fields_deg, WAVELENGTHS_UM)
        efl = float(np.asarray(optic.paraxial.f2()).item())
        epd = abs(float(np.asarray(optic.paraxial.EPD()).item()))
        if not np.isfinite(efl) or not np.isfinite(epd) or epd <= 0:
            raise ValueError("Finite EFL and positive finite entrance-pupil diameter are required.")
        fno = abs(efl) / epd
        _constraint(report, "EFL_mm", efl, spec.efl_mm * (1 - spec.efl_relative_tolerance), spec.efl_mm * (1 + spec.efl_relative_tolerance))
        _constraint(report, "F_number", fno, spec.f_number * (1 - spec.f_number_relative_tolerance), spec.f_number * (1 + spec.f_number_relative_tolerance))
        _constraint(report, "element_count", geometry["element_count"], spec.elements_min, spec.elements_max, 0)
        _constraint(report, "BFD_mm", geometry["bfd_mm"], spec.bfd_min_mm)
        if spec.track_max_mm is not None:
            _constraint(report, "total_track_mm", geometry["total_track_mm"], 0, spec.track_max_mm)
        _constraint(report, "minimum_center_thickness_mm", geometry["minimum_center_thickness_mm"], 2.0)
        _constraint(report, "minimum_edge_thickness_mm", geometry["minimum_edge_thickness_mm"], 1.0)
        offsets = _paraxial_focus_offsets(optic)
        report["paraxial"] = {"efl_mm": efl, "entrance_pupil_diameter_mm": epd, "f_number": fno,
                              "focus_offsets_from_sensor_mm": offsets, "axial_FC_mm": abs(offsets[0] - offsets[2])}
        if challenge == "doublet":
            _constraint(report, "EPD_mm", epd, 12.5, 12.5, 1e-6)
            _constraint(report, "axial_FC_mm", abs(offsets[0] - offsets[2]), 0, 0.10)
            powers = geometry["elements"]
            if len(powers) == 2:
                ordered = sorted(powers, key=lambda el: el["abbe_number"], reverse=True)
                if not (ordered[0]["abbe_number"] > ordered[1]["abbe_number"] and
                        ordered[0]["isolated_power_per_mm"] > 0 and ordered[1]["isolated_power_per_mm"] < 0):
                    report["violations"].append("Doublet requires positive higher-Abbe glass and negative lower-Abbe glass, using isolated thick-element power in air.")

        px, py, q = pupil_quadrature()
        rim_phi = 2 * np.pi * np.arange(RIM_SPOKES) / RIM_SPOKES
        check_px = np.r_[px, 0.0, RIM_RADIUS * np.cos(rim_phi)]
        check_py = np.r_[py, 0.0, RIM_RADIUS * np.sin(rim_phi)]
        fields = sorted(set(spec.fields_deg) | set(np.linspace(0, spec.fields_deg[-1], round(spec.fields_deg[-1] / spec.verification_step_deg) + 1).tolist()))
        report["settings"]["verification_fields_deg"] = fields
        ray_checks = []
        field_metrics = []
        all_rays_valid = True
        max_distortion = 0.0
        for angle in fields:
            bundles, chiefs = [], []
            for wavelength in WAVELENGTHS_UM:
                optic._judge_wavelength = wavelength
                xy, valid, diag = _trace_bundle(optic, angle, spec.fields_deg[-1], check_px, check_py, prescription["stop_radius_mm"])
                diag.update({"field_deg": angle, "wavelength_um": wavelength})
                ray_checks.append(diag)
                all_rays_valid &= bool(np.all(valid))
                if not np.all(valid):
                    report["violations"].append(f"Ray validation failed at {angle:g} deg, {wavelength:g} um: {diag['failed_rays']} of {diag['launched_rays']} samples.")
                bundles.append(xy[:len(q)])
                chiefs.append(xy[len(q)])
            if not all_rays_valid:
                continue
            distortion = 0.0 if angle == 0 else (chiefs[1][1] / (efl * np.tan(np.deg2rad(angle))) - 1)
            max_distortion = max(max_distortion, abs(float(distortion)))
            if angle in spec.fields_deg:
                fm = polychromatic_rms(np.asarray(bundles), q)
                fm.update({"field_deg": angle, "distortion_fraction": float(distortion),
                           "distortion_percent": 100 * float(distortion), "chief_image_xy_mm": np.asarray(chiefs).tolist(),
                           "chief_lateral_colour_FC_mm": float(np.linalg.norm(chiefs[0] - chiefs[2]))})
                field_metrics.append(fm)
        report["ray_checks"] = ray_checks
        report["field_metrics"] = field_metrics
        if not all_rays_valid:
            report["status"] = "ray_validation_failed"
            return report
        _constraint(report, "maximum_absolute_distortion_fraction", max_distortion, 0, spec.distortion_max)
        # A separate denser quadrature checks the score's numerical stability.
        dense_px, dense_py, dense_q = pupil_quadrature(2 * PUPIL_RINGS, 2 * PUPIL_SPOKES)
        dense_rms, dense_ok = [], True
        for angle in spec.fields_deg:
            bundle = []
            for wavelength in WAVELENGTHS_UM:
                optic._judge_wavelength = wavelength
                xy, valid, diag = _trace_bundle(optic, angle, spec.fields_deg[-1], dense_px, dense_py, prescription["stop_radius_mm"])
                if not np.all(valid):
                    dense_ok = False
                    report["violations"].append(f"Denser pupil validation failed at {angle:g} deg, {wavelength:g} um.")
                bundle.append(xy)
            if dense_ok:
                dense_rms.append(polychromatic_rms(np.asarray(bundle), dense_q)["rms_mm"])
        if not dense_ok:
            report["status"] = "ray_validation_failed"
            return report
        coarse_rms = np.array([f["rms_mm"] for f in field_metrics])
        dense_rms = np.array(dense_rms)
        difference = abs(dense_rms - coarse_rms)
        limit = np.maximum(RMS_CONVERGENCE_ABS_MM, RMS_CONVERGENCE_REL * dense_rms)
        converged = bool(np.all(difference <= limit))
        report["rms_convergence"] = {"dense_rings": 2 * PUPIL_RINGS, "dense_spokes": 2 * PUPIL_SPOKES,
                                      "dense_rms_mm": dense_rms.tolist(), "absolute_change_mm": difference.tolist(),
                                      "allowed_change_mm": limit.tolist(), "passed": converged}
        if not converged:
            report["violations"].append("RMS quadrature is not converged at the published tolerance; numerical review required.")
        if challenge == "wide_angle":
            coords = [(0.0, theta / spec.fields_deg[-1]) for theta in spec.fields_deg]
            fft_checks = []

            def validate_fft_snapshot(lens, pupil_x, pupil_y):
                _, valid, diagnostic = _validate_recorded_bundle(lens, pupil_x, pupil_y, prescription["stop_radius_mm"])
                fft_checks.append(diagnostic)
                if not np.all(valid):
                    raise ValueError(f"FFT grid ray validation failed: {diagnostic['failed_rays']} samples.")

            mtf = polychromatic_fft_mtf(optic, coords, WAVELENGTHS_UM, pupil_samples=256, fft_size=1024,
                                      snapshot_validator=validate_fft_snapshot)
            check = polychromatic_fft_mtf(optic, coords, WAVELENGTHS_UM, pupil_samples=512, fft_size=2048,
                                        snapshot_validator=validate_fft_snapshot)
            mtf_array = np.array([mtf["tangential"], mtf["sagittal"]])
            check_array = np.array([check["tangential"], check["sagittal"]])
            mtf_delta = float(np.max(abs(mtf_array - check_array)))
            report["mtf"] = mtf
            report["fft_ray_checks"] = fft_checks
            report["mtf_convergence"] = {"dense_pupil_samples": 512, "dense_fft_size": 2048,
                                          "maximum_absolute_change": mtf_delta, "allowed_change": MTF_CONVERGENCE_ABS,
                                          "passed": mtf_delta <= MTF_CONVERGENCE_ABS,
                                          "dense_tangential": check["tangential"], "dense_sagittal": check["sagittal"]}
            if mtf_delta > MTF_CONVERGENCE_ABS:
                report["violations"].append("MTF sampling is not converged at the published tolerance; numerical review required.")
            candidate_score = float(np.mean((1 - mtf_array) ** 2))
        else:
            candidate_score = float(np.mean((coarse_rms / spec.rms_scale_mm) ** 2))
        if not np.isfinite(candidate_score):
            raise ValueError("The final optical score is nonfinite.")
        report["diagnostic_optical_score"] = candidate_score
        report["eligible"] = not report["violations"]
        if report["eligible"]:
            report["status"] = "eligible"
            report["score"] = candidate_score
        elif all("numerical review required" in item for item in report["violations"]):
            report["status"] = "needs_numerical_review"
    except (ArithmeticError, ValueError, RuntimeError, TypeError, KeyError, IndexError) as exc:
        report["status"] = "evaluation_error"
        report["violations"].append(f"Evaluation failed: {type(exc).__name__}: {exc}")
    return report


def main() -> int:
    """Run the standalone evaluator and print its complete JSON report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prescription", type=Path)
    parser.add_argument("--challenge", choices=tuple(CHALLENGES), default="rms")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_design(json.loads(args.prescription.read_text()), args.challenge)
    output = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(output + "\n")
    print(output)
    return 0 if result["eligible"] else 2


if __name__ == "__main__":
    sys.exit(main())
