"""
QXU6028 Virtual Lab — unified reproduce pipeline
Runs L1, L2, L3 and writes a single results.json.

Usage:
    python src/reproduce.py data/regular_G13 outputs/regular
    python src/reproduce.py data/blind_G13  outputs/blind
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KB = 8.617333e-5      # eV / K
NA = 3.816e15         # cm^-2
ECHARGE = 1.602176634e-19
EMAX = 2.5            # eV

try:
    trapezoid = np.trapezoid
except AttributeError:
    trapezoid = np.trapz

SPEC_THRESHOLD = 0.030
RANDOM_SEED = 2026
N_NOISE = 500
N_BOOT = 200

# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------
def fermi(E, EF, T):
    x = np.clip((E - EF) / (KB * T), -60.0, 60.0)
    return 1.0 / (np.exp(x) + 1.0)

def jsonable(x):
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x

# ===========================================================================
# L1
# ===========================================================================
def n_band(EF, T, c):
    E = np.linspace(0.0, EMAX, 20001)
    return NA * trapezoid(c * E * fermi(E, EF, T), E)

def n_fermi(EF, T, c):
    E = np.linspace(EF, EMAX, 20001)
    return NA * trapezoid(c * E * fermi(E, EF, T), E)

def n_fermi_closed(EF, T, c):
    kT = KB * T
    return NA * c * kT * (EF * np.log(2.0) + (np.pi ** 2 / 12.0) * kT)

def run_l1(data_dir, out_dir):
    print("\n========== L1 ==========")
    l1_data = pd.read_csv(data_dir / "L1_data.csv")
    with open(data_dir / "L1_params.json", "r", encoding="utf-8") as f:
        params = json.load(f)

    c = float(params["c"])
    T = float(params["T"])
    EF_op = float(params["EF_op_eV"])
    rho_sq = float(params["rho_ohm_sq"])
    print(f"c={c:.6e}, T={T:.2f} K, EF_op={EF_op:.4f} eV, rho={rho_sq:.6e}")

    # gate checks
    tests = [(0.000, 1.00), (0.073, 2.00), (0.100, 2.60), (0.200, 5.10)]
    all_pass = True
    for ef, target in tests:
        ratio = n_band(ef, T, c) / n_fermi(ef, T, c)
        rel_err = abs(ratio - target) / target
        ok = rel_err < 0.05
        all_pass &= ok
        print(f"  EF={ef:.3f}: ratio={ratio:.4f} target={target:.2f} {'PASS' if ok else 'FAIL'}")
    if not all_pass:
        raise SystemExit("L1 gate checks FAILED")

    ef_array = l1_data["EF_eV"].values
    nb_sweep = l1_data["n_band_cm2"].values
    nf_sweep = np.array([n_fermi(ef, T, c) for ef in ef_array])
    C_sweep = nb_sweep / nf_sweep

    nb_op = n_band(EF_op, T, c)
    nf_op = n_fermi(EF_op, T, c)
    correction_factor = nb_op / nf_op
    mu_corr = 1.0 / (ECHARGE * nf_op * rho_sq)

    print(f"correction_factor = {correction_factor:.6f}")
    print(f"n_fermi_op_cm2    = {nf_op:.6e}")
    print(f"mobility_corrected = {mu_corr:.4f}")

    # figure
    plt.figure(figsize=(8, 5))
    plt.plot(ef_array, C_sweep, lw=2, label=r"$C(E_F)=n_{band}/n_F$")
    plt.axhline(2.0, ls="--", color="orange")
    plt.axhline(4.0, ls="--", color="red")
    plt.axvline(EF_op, ls=":", color="green", label=f"EF_op={EF_op:.3f} eV")
    plt.xlabel(r"$E_F$ (eV)")
    plt.ylabel(r"$C(E_F)$")
    plt.title("L1: band-edge vs Fermi-referenced count")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "L1_Curve.png", dpi=200)
    plt.close()

    return {
        "correction_factor": float(correction_factor),
        "n_fermi_op_cm2": float(nf_op),
        "mobility_corrected_cm2_Vs": float(mu_corr),
    }

# ===========================================================================
# L2
# ===========================================================================
def dos(E, model, c=1.0, Eg=0.0):
    if model == "cone":
        return c * np.abs(E)
    D = Eg / 2.0
    return np.where(np.abs(E) > D, c * (np.abs(E) - D), 0.0)

def carrier_np(EF, T, model, c=1.0, Eg=0.0, npts=4000):
    E = np.linspace(-EMAX, EMAX, npts)
    f = fermi(E, EF, T)
    g = dos(E, model, c, Eg)
    n = NA * trapezoid(np.where(E >= EF, g * f, 0.0), E)
    p = NA * trapezoid(np.where(E <= EF, g * (1.0 - f), 0.0), E)
    return n, p

def build_model_library(T):
    EF_grid = np.linspace(-8 * KB * T, 9 * KB * T, 400)
    gaps_kT = np.arange(0.5, 8.0 + 1e-9, 0.25)
    models = []

    RH, RS = [], []
    for EF in EF_grid:
        n, p = carrier_np(EF, T, "cone", c=1.0, Eg=0.0)
        RH.append((p - n) / ((p + n) ** 2))
        RS.append(1.0 / (p + n))
    RH = np.array(RH); RS = np.array(RS)
    models.append({
        "name": "cone", "Eg_kT": 0.0, "EF_grid": EF_grid,
        "RH_norm": RH / np.max(np.abs(RH)),
        "RS_norm": RS / np.max(RS),
    })

    for Eg_kT in gaps_kT:
        Eg = Eg_kT * KB * T
        RH, RS = [], []
        for EF in EF_grid:
            n, p = carrier_np(EF, T, "gap", c=1.0, Eg=Eg)
            RH.append((p - n) / ((p + n) ** 2))
            RS.append(1.0 / (p + n))
        RH = np.array(RH); RS = np.array(RS)
        models.append({
            "name": "gap", "Eg_kT": float(Eg_kT), "EF_grid": EF_grid,
            "RH_norm": RH / np.max(np.abs(RH)),
            "RS_norm": RS / np.max(RS),
        })
    return models

def nearest_curve_rms(RH_data_norm, RS_data_norm, model):
    data_xy = np.column_stack([RH_data_norm, RS_data_norm])
    model_xy = np.column_stack([model["RH_norm"], model["RS_norm"]])
    d2 = ((data_xy[:, None, :] - model_xy[None, :, :]) ** 2).sum(axis=2)
    j_nearest = np.argmin(d2, axis=1)
    rms = np.sqrt(np.mean(np.min(d2, axis=1)))
    return rms, model["EF_grid"][j_nearest]

def select_model(RH_data_norm, RS_data_norm, models):
    cone = models[0]
    r_cone, EF_cone = nearest_curve_rms(RH_data_norm, RS_data_norm, cone)
    best_gap = None
    best_r_gap = np.inf
    best_EF_gap = None
    for m in models[1:]:
        r, EF = nearest_curve_rms(RH_data_norm, RS_data_norm, m)
        if r < best_r_gap:
            best_r_gap = r
            best_gap = m
            best_EF_gap = EF
    if best_gap is not None and best_r_gap < 0.85 * r_cone and best_gap["Eg_kT"] >= 1.0:
        return {
            "model_name": "hard_gap", "Eg_kT": best_gap["Eg_kT"],
            "r_cone": r_cone, "r_gap_best": best_r_gap,
            "EF_assigned": best_EF_gap, "selected_model": best_gap,
        }
    return {
        "model_name": "cone", "Eg_kT": 0.0,
        "r_cone": r_cone, "r_gap_best": best_r_gap,
        "EF_assigned": EF_cone, "selected_model": cone,
    }

def run_l2(data_dir, out_dir):
    print("\n========== L2 ==========")
    df = pd.read_csv(data_dir / "L2_data.csv")
    with open(data_dir / "L2_meta.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    T = float(meta["T_K"])

    idxs = np.sort(df["measurement_index"].unique())
    RH_mean, RS_mean = [], []
    RH_reps, RS_reps = [], []
    for idx in idxs:
        sub = df[df["measurement_index"] == idx]
        rh = sub["R_H_raw"].to_numpy(dtype=float)
        rs = sub["R_xx_raw"].to_numpy(dtype=float)
        RH_mean.append(np.mean(rh))
        RS_mean.append(np.mean(rs))
        RH_reps.append(rh)
        RS_reps.append(rs)

    RH_mean = np.array(RH_mean)
    RS_mean = np.array(RS_mean)
    RH_mean_norm = RH_mean / np.max(np.abs(RH_mean))
    RS_mean_norm = RS_mean / np.max(RS_mean)

    models = build_model_library(T)
    central = select_model(RH_mean_norm, RS_mean_norm, models)
    print(f"model = {central['model_name']}, Eg_kT = {central['Eg_kT']:.4f}")
    print(f"r_cone = {central['r_cone']:.6f}, r_gap_best = {central['r_gap_best']:.6f}")

    # figures
    plt.figure(figsize=(8, 4))
    for i, idx in enumerate(idxs):
        plt.scatter([idx] * len(RH_reps[i]), RH_reps[i], s=10, alpha=0.6)
    plt.axhline(0, color="k", lw=0.8)
    sc = np.where(np.diff(np.sign(RH_mean)) != 0)[0]
    if len(sc) > 0:
        plt.axvspan(idxs[sc[0]], idxs[sc[0] + 1], alpha=0.2, color="red")
    plt.xlabel("measurement_index")
    plt.ylabel("R_H_raw")
    plt.title("L2 raw R_H repeats")
    plt.tight_layout()
    plt.savefig(out_dir / "L2_raw_RH_repeats.png", dpi=200)
    plt.close()

    plt.figure(figsize=(6, 5))
    plt.scatter(RH_mean_norm, RS_mean_norm, c="k", label="mean data", zorder=5)
    m = central["selected_model"]
    plt.plot(m["RH_norm"], m["RS_norm"], "r-",
             label=f"{central['model_name']} (Eg/kT={central['Eg_kT']:.2f})")
    plt.xlabel(r"normalised $\tilde R_H$")
    plt.ylabel(r"normalised $\tilde R_{xx}$")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "L2_model_space.png", dpi=200)
    plt.close()

    # bootstrap
    rng = np.random.default_rng(12345)
    boot_Eg = []
    boot_EF = np.zeros((N_BOOT, len(idxs)))
    for b in range(N_BOOT):
        RH_b, RS_b = [], []
        for i in range(len(idxs)):
            k = rng.integers(0, len(RH_reps[i]))
            RH_b.append(RH_reps[i][k])
            RS_b.append(RS_reps[i][k])
        RH_b = np.array(RH_b); RS_b = np.array(RS_b)
        RH_b_norm = RH_b / np.max(np.abs(RH_b))
        RS_b_norm = RS_b / np.max(RS_b)
        sel = select_model(RH_b_norm, RS_b_norm, models)
        boot_Eg.append(sel["Eg_kT"])
        boot_EF[b, :] = sel["EF_assigned"]

    boot_Eg = np.array(boot_Eg)
    Eg_p16 = float(np.percentile(boot_Eg, 16))
    Eg_p84 = float(np.percentile(boot_Eg, 84))
    EF_p16 = np.percentile(boot_EF, 16, axis=0)
    EF_p84 = np.percentile(boot_EF, 84, axis=0)

    plt.figure(figsize=(8, 4))
    EF_central = central["EF_assigned"]
    yerr = np.vstack([np.abs(EF_central - EF_p16), np.abs(EF_p84 - EF_central)])
    plt.errorbar(idxs, EF_central, yerr=yerr, fmt="o-", capsize=3)
    plt.xlabel("measurement_index")
    plt.ylabel("assigned E_F (eV)")
    plt.title("L2 Fermi trajectory with bootstrap 16-84%")
    plt.tight_layout()
    plt.savefig(out_dir / "L2_EF_trajectory.png", dpi=200)
    plt.close()

    return {
        "model": central["model_name"],
        "Eg_kT": central["Eg_kT"],
        "Eg_uncertainty_kT": (Eg_p84 - Eg_p16) / 2.0,
        "EF_trajectory_eV": EF_central.tolist(),
    }

# ===========================================================================
# L3
# ===========================================================================
def gradient_matrix(npix=10):
    rows = []
    Nloc = npix * npix
    for i in range(npix):
        for j in range(npix):
            k = i * npix + j
            if j < npix - 1:
                r = np.zeros(Nloc); r[k] = -1.0; r[k + 1] = 1.0
                rows.append(r)
            if i < npix - 1:
                r = np.zeros(Nloc); r[k] = -1.0; r[k + npix] = 1.0
                rows.append(r)
    return np.asarray(rows)

def make_projector(N):
    one = np.ones((N, 1)) / np.sqrt(N)
    return np.eye(N) - one @ one.T

def reconstruct(dvec, A, L, P, eta):
    M = P @ (A.T @ A + eta * (L.T @ L)) @ P + 1e-9 * np.eye(A.shape[1])
    b = P @ (A.T @ dvec)
    m = np.linalg.lstsq(M, b, rcond=None)[0]
    return m - m.mean()

def point_spread_fwhm(pixel_index, A, L, P, eta, npix=10):
    q = np.zeros(npix * npix); q[pixel_index] = 1.0; q -= q.mean()
    y = A @ q
    qhat = reconstruct(y, A, L, P, eta)
    centers = np.linspace(-2.7, 2.7, npix)
    inj_i, inj_j = divmod(pixel_index, npix)
    X, Y = np.meshgrid(centers, centers)
    r = np.sqrt((X - centers[inj_j]) ** 2 + (Y - centers[inj_i]) ** 2).ravel()
    w = np.maximum(qhat, 0.0)
    if np.sum(w) <= 0:
        return float("nan"), qhat
    sigma2 = np.sum(w * r ** 2) / (2.0 * np.sum(w))
    return float(2.355 * np.sqrt(sigma2)), qhat

def run_l3(data_dir, out_dir):
    print("\n========== L3 ==========")
    A = np.load(data_dir / "L3_A.npy")
    d_reps = np.loadtxt(data_dir / "L3_d.csv", delimiter=",")
    print(f"A shape {A.shape}, d shape {d_reps.shape}")
    assert A.shape == (128, 100)
    assert d_reps.shape == (3, 128)
    assert np.max(np.abs(A.sum(axis=1))) < 1e-11

    NPIX = 10
    N = NPIX * NPIX
    dbar = d_reps.mean(axis=0)
    L = gradient_matrix(NPIX)
    P = make_projector(N)
    eta0 = 1e-2 * np.linalg.norm(A, 2) ** 2 / np.linalg.norm(L, 2) ** 2
    print(f"eta0 = {eta0:.6e}")

    mhat = reconstruct(dbar, A, L, P, eta0)
    mhat_map = mhat.reshape(NPIX, NPIX)
    print(f"max|mhat| = {np.max(np.abs(mhat)):.6f}")

    # eta sensitivity figure
    etas = eta0 * np.array([0.01, 0.1, 1.0, 10.0, 100.0])
    rn, gn = [], []
    for eta in etas:
        m = reconstruct(dbar, A, L, P, eta)
        rn.append(np.linalg.norm(A @ m - dbar))
        gn.append(np.linalg.norm(L @ m))
    plt.figure(figsize=(6, 4))
    plt.loglog(gn, rn, "o-")
    plt.xlabel(r"roughness $\|Lm\|$")
    plt.ylabel(r"residual $\|Am-\bar d\|$")
    plt.title("L3 eta sensitivity")
    plt.tight_layout()
    plt.savefig(out_dir / "L3_method.png", dpi=200)
    plt.close()

    # features
    centers = np.linspace(-2.7, 2.7, NPIX)
    imax = np.unravel_index(np.argmax(mhat_map), mhat_map.shape)
    imin = np.unravel_index(np.argmin(mhat_map), mhat_map.shape)
    features = [
        {"type": "positive", "value": float(mhat_map[imax]),
         "row": int(imax[0]), "col": int(imax[1]),
         "x_probe_pitch": float(centers[imax[1]]),
         "y_probe_pitch": float(centers[imax[0]])},
        {"type": "negative", "value": float(mhat_map[imin]),
         "row": int(imin[0]), "col": int(imin[1]),
         "x_probe_pitch": float(centers[imin[1]]),
         "y_probe_pitch": float(centers[imin[0]])},
    ]

    fwhm_c, _ = point_spread_fwhm(5 * NPIX + 5, A, L, P, eta0, NPIX)
    fwhm_o, _ = point_spread_fwhm(2 * NPIX + 2, A, L, P, eta0, NPIX)
    resolution = float(np.nanmax([fwhm_c, fwhm_o]))
    print(f"resolution = {resolution:.4f}")

    sigma_j = d_reps.std(axis=0, ddof=1)
    rng = np.random.default_rng(RANDOM_SEED)
    max_abs_noise = []
    for _ in range(N_NOISE):
        noise = rng.normal(0.0, sigma_j)
        m_noise = reconstruct(noise, A, L, P, eta0)
        max_abs_noise.append(np.max(np.abs(m_noise)))
    delta95 = float(np.percentile(max_abs_noise, 95))
    print(f"delta95 = {delta95:.6f}")

    a = float(np.max(np.abs(mhat)))
    if a + delta95 <= SPEC_THRESHOLD:
        passed, confidence = True, "clear_pass"
    elif a - delta95 > SPEC_THRESHOLD:
        passed, confidence = False, "clear_fail"
    else:
        passed, confidence = bool(a <= SPEC_THRESHOLD), "borderline"
    print(f"a = {a:.6f}, pass = {passed}, confidence = {confidence}")

    plt.figure(figsize=(6, 5))
    plt.imshow(mhat_map, origin="lower",
               extent=[centers[0], centers[-1], centers[0], centers[-1]],
               cmap="RdBu_r", aspect="equal")
    plt.colorbar(label="reconstructed amplitude")
    plt.scatter([f["x_probe_pitch"] for f in features],
                [f["y_probe_pitch"] for f in features],
                c="k", marker="x", s=60)
    plt.xlabel("x / probe pitch")
    plt.ylabel("y / probe pitch")
    plt.title("L3 zero-mean reconstructed map")
    plt.tight_layout()
    plt.savefig(out_dir / "L3_map.png", dpi=200)
    plt.close()

    return {
        "map": mhat.tolist(),
        "features": features,
        "resolution_probe_pitch": resolution,
        "detection_limit_fraction": delta95,
        "pass": passed,
        "confidence": confidence,
    }

# ===========================================================================
# Main
# ===========================================================================
def main():
    if len(sys.argv) < 3:
        print("Usage: python src/reproduce.py <data_dir> <out_dir>")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        raise SystemExit(f"Data dir not found: {data_dir}")

    dataset_set = "blind" if "blind" in str(out_dir).lower() else "regular"
    print(f"Data dir: {data_dir}")
    print(f"Output dir: {out_dir}")
    print(f"dataset_set: {dataset_set}")

    l1 = run_l1(data_dir, out_dir)
    l2 = run_l2(data_dir, out_dir)
    l3 = run_l3(data_dir, out_dir)

    results = {
        "schema_version": "QXU6028-results-v1",
        "group": "G13",
        "dataset_set": dataset_set,
        "pipeline_commit": "REPLACE_WITH_GIT_COMMIT_HASH",
        "L1": l1,
        "L2": l2,
        "L3": l3,
    }

    with open(out_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(jsonable(results), f, indent=2)

    print(f"\nWrote {out_dir / 'results.json'}")

if __name__ == "__main__":
    main()
