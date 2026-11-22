from pathlib import Path
import argparse
import hashlib
import json
import subprocess

import numpy as np

KB = 8.617333e-5
AREAL_DENSITY = 3.816e15
CHARGE = 1.602176634e-19


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fermi(energy, ef, kt):
    return 1 / (1 + np.exp(np.clip((energy - ef) / kt, -60, 60)))


def l1(data):
    params = read_json(data / "L1_params.json")
    rows = np.genfromtxt(data / "L1_data.csv", delimiter=",", names=True)
    kt, c = KB * params["T"], params["c"]
    ef_op, rho = params["EF_op_eV"], params["rho_ohm_sq"]

    def band(ef):
        e = np.linspace(0, 2.5, 20001)
        return AREAL_DENSITY * c * np.trapezoid(e * fermi(e, ef, kt), e)

    def window(ef):
        return AREAL_DENSITY * c * kt * (ef * np.log(2) + np.pi**2 * kt / 12)

    gates = [band(e) / window(e) for e in [0, .1, .2]]
    if params["T"] == 300:
        assert np.allclose(gates, [1, 2.6, 5.1], atol=.04)
    e = np.linspace(ef_op, 2.5, 20001)
    crosscheck = AREAL_DENSITY * c * np.trapezoid(e * fermi(e, ef_op, kt), e)
    assert np.isclose(crosscheck, window(ef_op), rtol=1e-5)

    sweep = rows["EF_eV"]
    nb, nf = rows["n_band_cm2"], window(sweep)
    assert np.all(np.diff(nb / nf) > 0)
    smooth_ef = np.linspace(0, max(.25, max(sweep)), 301)
    smooth_ratio = np.array([band(e) / window(e) for e in smooth_ef])
    crossings = np.interp([2, 4], smooth_ratio, smooth_ef)
    nb_op, nf_op = band(ef_op), window(ef_op)
    result = dict(correction_factor=nb_op/nf_op, n_fermi_op_cm2=nf_op,
                  mobility_corrected_cm2_Vs=1/(CHARGE*nf_op*rho))
    metrics = dict(ef_op=ef_op, rho=rho, temperature=params["T"], c=c, nb_op=nb_op,
                   mobility_band=1/(CHARGE*nb_op*rho), gates=gates,
                   crossings=crossings.tolist(), l1_numeric_rel_error=abs(crosscheck/nf_op-1),
                   l1_csv_rel_error=float(np.max(np.abs(np.array([band(e) for e in sweep])/nb-1))))
    plots = dict(sweep=sweep, nb=nb, nf=nf, smooth_ef=smooth_ef, smooth_ratio=smooth_ratio)
    return result, metrics, plots


def normalize(pairs):
    return pairs / np.array([np.max(np.abs(pairs[:, 0])), np.max(pairs[:, 1])])


def l2(data):
    meta = read_json(data / "L2_meta.json")
    rows = np.genfromtxt(data / "L2_data.csv", delimiter=",", names=True)
    indices = np.unique(rows["measurement_index"]).astype(int)
    repeats = np.unique(rows["repeat"])
    scans = []
    for idx in indices:
        block = np.sort(rows[rows["measurement_index"] == idx], order="repeat")
        assert len(repeats) == 3 and np.array_equal(block["repeat"], repeats)
        scans.append(np.column_stack([block["R_H_raw"], block["R_xx_raw"]]))
    scans = np.array(scans)
    mean = scans.mean(axis=1)
    brackets = np.flatnonzero((mean[:-1, 0] * mean[1:, 0]) <= 0)
    assert brackets.size > 0
    measured = normalize(mean)
    assert np.array_equal(np.sign(mean[:, 0]), np.sign(measured[:, 0]))

    kt = KB * meta["T_K"]
    ef = kt * np.linspace(-8, 9, 400)
    energy = np.linspace(-2.5, 2.5, 4000)
    f = fermi(energy[None, :], ef[:, None], kt)
    above = energy[None, :] >= ef[:, None]
    below = energy[None, :] <= ef[:, None]
    gaps = np.r_[0, np.arange(.5, 8.01, .25)]
    models = []
    for gap in gaps:
        dos = AREAL_DENSITY * np.maximum(np.abs(energy) - gap*kt/2, 0)
        n = np.trapezoid(above * f * dos, energy, axis=1)
        p = np.trapezoid(below * (1-f) * dos, energy, axis=1)
        models.append(normalize(np.column_stack([(p-n)/(p+n)**2, 1/(p+n)])))
    models = np.array(models)

    def fit(pairs):
        d2 = ((models[:, None, :, :] - pairs[None, :, None, :])**2).sum(axis=-1)
        nearest = d2.argmin(axis=2)
        rms = np.sqrt(d2.min(axis=2).mean(axis=1))
        best_gap = 1 + rms[1:].argmin()
        chosen = best_gap if rms[best_gap] < .85*rms[0] and gaps[best_gap] >= 1 else 0
        return chosen, best_gap, rms, ef[nearest[chosen]]

    chosen, best_gap, rms, trajectory = fit(measured)
    assert len(trajectory) == len(indices)
    rng = np.random.default_rng(602802)
    boot_gap, boot_ef = [], []
    for _ in range(200):
        replicate = scans[np.arange(len(indices)), rng.integers(0, 3, len(indices))]
        selected, _, _, assigned = fit(normalize(replicate))
        boot_gap.append(gaps[selected])
        boot_ef.append(assigned)
    gap_lo, gap_median, gap_hi = np.percentile(boot_gap, [16, 50, 84])
    ef_lo, ef_hi = np.percentile(boot_ef, [16, 84], axis=0)
    result = dict(model="hard_gap" if chosen else "cone", Eg_kT=float(gaps[chosen]),
                  Eg_uncertainty_kT=float((gap_hi-gap_lo)/2), EF_trajectory_eV=trajectory.tolist())
    metrics = dict(n_indices=len(indices), brackets=[[int(indices[i]), int(indices[i+1])] for i in brackets],
                   cone_rms=float(rms[0]), best_hard_gap_kT=float(gaps[best_gap]),
                   hard_gap_rms=float(rms[best_gap]), gap_boot=[gap_lo, gap_median, gap_hi],
                   hard_gap_fraction=float(np.mean(np.array(boot_gap)>0)),
                   trajectory_min=float(min(trajectory)), trajectory_max=float(max(trajectory)),
                   trajectory_first=float(trajectory[0]), trajectory_last=float(trajectory[-1]),
                   median_ef_interval=float(np.median(ef_hi-ef_lo)), kt=kt)
    plots = dict(indices=indices, scans=scans, measured=measured, models=models, gaps=gaps,
                 rms=rms, selected=chosen, ef=ef, trajectory=trajectory, ef_lo=ef_lo, ef_hi=ef_hi)
    return result, metrics, plots


def l3(data, spec):
    a = np.load(data / "L3_A.npy", allow_pickle=False)
    repeats = np.loadtxt(data / "L3_d.csv", delimiter=",")
    assert a.shape == (128, 100) and repeats.shape == (3, 128)
    row_sum = np.max(np.abs(a.sum(axis=1)))
    assert row_sum < 1e-11
    d = repeats.mean(axis=0)
    sigma = repeats.std(axis=0, ddof=1)
    eye = np.eye(100)
    ids = np.arange(100).reshape(10, 10)
    left, right = ids[:, :-1].ravel(), ids[:, 1:].ravel()
    top, bottom = ids[:-1, :].ravel(), ids[1:, :].ravel()
    gradient = np.vstack([eye[right]-eye[left], eye[bottom]-eye[top]])
    projector = eye - np.ones((100, 100))/100
    s = np.linalg.svd(a, compute_uv=False)
    eta = .01*s[0]**2/np.linalg.norm(gradient, 2)**2

    def inverse(strength):
        mat = projector @ (a.T @ a + strength*(gradient.T @ gradient)) @ projector + 1e-9*eye
        return projector @ np.linalg.solve(mat, projector @ a.T)

    inv = inverse(eta)
    m = inv @ d
    assert abs(m.mean()) < 1e-12
    multipliers = np.array([.01, .1, 1, 10, 100])
    alt = np.stack([inverse(eta*f) @ d for f in multipliers])
    residual = np.linalg.norm(alt @ a.T - d, axis=1)
    roughness = np.linalg.norm(alt @ gradient.T, axis=1)
    coords = np.linspace(-2.7, 2.7, 10)
    x, y = np.meshgrid(coords, coords)
    peaks = [int(np.argmax(m)), int(np.argmin(m))]
    features = [dict(x=float(x.flat[i]), y=float(y.flat[i]),
                     sign="positive" if m[i] > 0 else "negative", amplitude=float(m[i])) for i in peaks]
    responses, widths = [], []
    for r, c in [(5, 5), (2, 7)]:
        injected = projector[:, ids[r,c]]
        response = inv @ (a @ injected)
        w = np.maximum(response, 0)
        radius_sq = (x.ravel()-coords[c])**2 + (y.ravel()-coords[r])**2
        widths.append(float(2.355*np.sqrt((w@radius_sq)/(2*w.sum()))))
        responses.append(response)
    rng = np.random.default_rng(602803)
    noise_maps = rng.normal(0, sigma, (500, 128)) @ inv.T
    max_noise = np.max(np.abs(noise_maps), axis=1)
    delta = float(np.percentile(max_noise, 95))
    amplitude = float(np.max(np.abs(m)))
    status = "clear pass" if amplitude+delta < spec else "clear fail" if amplitude-delta > spec else "borderline"
    result = dict(map=m.tolist(), features=features, resolution_probe_pitch=max(widths),
                  detection_limit_fraction=delta, **{"pass": amplitude <= spec}, confidence=status)
    metrics = dict(eta=eta, row_sum=float(row_sum), map_mean=float(m.mean()), widths=widths,
                   spec=spec, amplitude=amplitude, interval=[max(0.,amplitude-delta),amplitude+delta],
                   noise_rms=float(np.sqrt(np.mean(sigma**2))),
                   noise_limit_mean=float(np.percentile(max_noise/np.sqrt(3),95)),
                   singular_max=float(s[0]), singular_min=float(s[-1]),
                   rank=int(np.linalg.matrix_rank(a)), residuals=residual.tolist(),
                   roughnesses=roughness.tolist(), sensitivity_peaks=np.max(np.abs(alt),axis=1).tolist())
    plots = dict(coords=coords, map=m.reshape(10,10), responses=np.reshape(responses,(2,10,10)),
                 singular=s, multipliers=multipliers, residual=residual, roughness=roughness,
                 max_noise=max_noise)
    return result, metrics, plots


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=root/"data")
    parser.add_argument("--out", type=Path, default=root/"generated")
    parser.add_argument("--spec", type=float, default=.030)
    args = parser.parse_args()
    meta = read_json(args.data/"L1_params.json")
    manifest = args.data/"manifest.json"
    if manifest.exists():
        for f in read_json(manifest)["files"]:
            assert hashlib.sha256((args.data/f["name"]).read_bytes()).hexdigest() == f["sha256"], f["name"]
    try:
        commit = subprocess.check_output(["git","rev-parse","HEAD"], cwd=root,
                                         stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = (root/"pipeline_commit.txt").read_text().strip() if (root/"pipeline_commit.txt").exists() else "unversioned"
    result = read_json(args.data/"results_template.json")
    result.update(group=meta["group"], dataset_set=meta["dataset_set"], pipeline_commit=commit)
    r1,m1,p1 = l1(args.data)
    r2,m2,p2 = l2(args.data)
    r3,m3,p3 = l3(args.data,args.spec)
    result.update(L1=r1,L2=r2,L3=r3)
    args.out.mkdir(parents=True,exist_ok=True)
    dump(args.out/("blind_results.json" if meta["dataset_set"]=="blind" else "results.json"), result)
    dump(args.out/"analysis_metrics.json", {**m1,**m2,**m3})
    np.savez(args.out/"plot_data.npz", **p1, **p2, **p3)
    from figures import write_figures
    write_figures(args.out, {**p1,**p2,**p3}, result, {**m1,**m2,**m3})
    print(f'{meta["group"]} {meta["dataset_set"]}, commit {commit}')
    print(f'L1 C={r1["correction_factor"]:.6g} | L2 {r2["model"]} Eg/kT={r2["Eg_kT"]:.3g} | L3 {r3["confidence"]}')

if __name__ == "__main__":
    main()
