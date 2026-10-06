"""blobkit.soup.sim_gpu — JAX accelerator port of the L0 blob soup simulator.

MERGED verbatim from probes/blobs/gpu/blobgpu/{core,packing,soup}.py (the
correctness-gated blobgpu package; see its GATES.md):
  * f64 trajectory parity: rel L2 < 1e-5 at T=100tu vs genome.py/soup_sim f64
  * descriptor parity: locked metrics_v1 battery on the 7 ground truths
  * bond anchors: A4s pair d*=15.40 @ dt=0.02; A5 pair d*=15.70 @ dt=0.005

jax is imported LAZILY (_jax()): importing this module without jax installed
works; calling any GPU entry point raises ImportError with install advice.
Install: pip install 'blobkit[gpu]'.

Layout of this file: [core] jitted stepper -> [packing] genome/state padding
-> [soup] drop-in init/advance/snapshot drivers (single + batched).
Numerics contract mirrors blobkit.soup.sim_cpu.advance (the LOCKED CPU
kernel); RNG is jax threefry folded on absolute step (chunk-exact), a
DIFFERENT stream than CPU PCG64 — parity is gated at noise=0 (f64 rel-L2)
and at descriptor level with noise. See original module docstrings below.

--- core.py original docstring ---
blobgpu/core.py — JAX stepper for the L0 genome simulator (batched, padded).

Numerics contract (mirrors probes/blobs/l0/complexity/soup_sim_v2.advance,
the LOCKED CPU kernel). One step, in this order:
  1. explicit reaction with OLD u:  R_u = lam*u - u^3 + k1 - K@x (- bilin)
                                    R_x = (drive(z) - x) / tau,  z = u - u0
  2. F += dt * R
  3. optional activator noise (amplitude noise*sqrt(dt))
  4. exact diffusion in k-space:    F <- irfft2( rfft2(F) * exp(-D k^2 dt) )

Batch layout: F is ONE tensor (B, nf_max, N, N); worlds are padded to a common
(na_max, nc_max). Padded slots are inert BY PARAMETER CONSTRUCTION (packing.py;
verified exactly in tests/test_padding.py). There is NO cross-world coupling:
reactions are per-world einsums over the field axis, FFTs are per-field 2D
transforms. A NaN blowup in one world cannot contaminate another.

RNG: per-world jax threefry keys, folded with the ABSOLUTE step index, so
(a) chunked continuation reproduces a single long run exactly, and
(b) a world's noise stream does not depend on what else is in the batch.
This is a different stream than the CPU numpy PCG64 stream — same law
(N(0,1)*noise*sqrt(dt) on activators), different realization. Trajectory
parity is therefore gated at noise=0 (f64 rel-L2) and, with noise, at the
descriptor level (locked metrics_v1 battery). See GATES.md.

f32 default; f64 via JAX_ENABLE_X64=1 (or core.enable_x64() first thing).
einsums pinned to Precision.HIGHEST: on A100 the default would let XLA use
TF32 tensor cores for f32 contractions — a silent 1e-3-level numerics change.
--- packing.py original docstring ---
blobgpu/packing.py — genomes -> padded parameter tensors for the batched stepper.

A batch of B genomes is padded to a common (na_max, nc_max) field layout.
Padded slots are inert BY PARAMETER CONSTRUCTION (verified in tests/test_padding.py):
  activator pad: lam=k1=u0=0, K row=0, noise masked  -> du/dt = -u^3, u==0 stays 0
  channel  pad: inv_tau=0, W rows=0, K cols=0        -> dx/dt = 0
  diffusion pad: D=0 -> E=1 (identity in k-space)
so a padded field that starts at 0 stays exactly 0 and couples to nothing.
There is no cross-world term anywhere; each world's trajectory equals its
unpadded single-world trajectory bit-for-bit (same dtype, same backend).

Layout of the packed state: F (B, nf_max, N, N) with fields [acts | chans].
--- soup.py original docstring ---
blobgpu/soup.py — drop-in GPU backend for the S1 soup assay (soup_sim_v2).

Contract: identical records to soup_sim_v2 (ts/blobs/mass/ct/patches/orgs/memf/
snaps + snapshot_rec keys). ICs are built by soup_sim_v2.init_soup itself
(same numpy RNG -> bit-identical seeded states). Only the stepping loop is
swapped: chunks of REC (250 steps) run on the JAX device (fori_loop inside one
jit), fields are pulled to host at each record point and fed to the verbatim
CPU _record. Blob tracking stays on CPU (locked measurement code).

Noise: jax threefry (per-world key, folded on absolute step + field index).
Different stream than CPU PCG64, same law -> descriptor-level parity gate.
Chunked continuation is bitwise-identical to a single long GPU run at the same
final T (absolute-step key folds; verified in tests/test_chunking.py).

Usage:
  S = init_soup_gpu(g, L=128.0, seed=1)              # single world
  advance_gpu(S, 2500.0); rec = snapshot_rec_gpu(S)  # same as v2

  SS = init_soup_gpu_batch([(g1, 1), (g2, 1), ...])  # one tensor, B worlds
  advance_gpu_batch(SS, 2500.0)
  recs = [snapshot_rec_gpu(S) for S in SS["worlds"]]

Do NOT wire into the live v2 run; this is the future-swap hook.
"""

# ======================================================= [core.py verbatim]

from functools import partial

import numpy as np


def _jax():
    """Lazy jax import: blobkit installs without jax; GPU paths need extras
    [gpu]. [blobkit edit E15]"""
    try:
        import jax
        import jax.numpy as jnp
    except ImportError as e:                      # pragma: no cover
        raise ImportError(
            "blobkit.soup.sim_gpu needs jax. Install the gpu extra: "
            "pip install 'blobkit[gpu]' (JAX>=0.4.38; Blackwell GPUs need a "
            "CUDA>=12.8 wheel, validated with jax[cuda12] 0.11.2).") from e
    return jax, jnp


def enable_x64():
    jax, _ = _jax()
    jax.config.update("jax_enable_x64", True)


# ----------------------------------------------------------------- k-space
def k2_grid(N, dx):
    kf = 2 * np.pi * np.fft.fftfreq(N, d=dx)
    kr = 2 * np.pi * np.fft.rfftfreq(N, d=dx)
    return kf[:, None] ** 2 + kr[None, :] ** 2          # (N, N//2+1), f64


def diffusion_E(D, N, dx, dt, dtype=np.float32):
    """exp(-D k^2 dt): computed in f64, cast to dtype (CPU convention).
    D: (B, nf) -> E: (B, nf, N, N//2+1) real."""
    _, jnp = _jax()                               # [blobkit edit E16]
    k2 = k2_grid(N, dx)
    E = np.exp(-np.asarray(D, np.float64)[..., None, None] * k2[None, None] * dt)
    return jnp.asarray(E.astype(dtype))


def batch_keys(seeds):
    """Per-world PRNG keys from integer seeds -> (B, 2) uint32."""
    jax, jnp = _jax()                             # [blobkit edit E17]
    return jnp.stack([jax.random.PRNGKey(int(s)) for s in seeds])


# ----------------------------------------------------------------- stepper
def make_stepper(struct, N, dx, dt, noise=0.0, precompute_E=True, unfused=False):
    """Build the jitted chunk stepper for a packed batch.

    struct: static ints/tuples from packing.pack_genomes().
    Returns step_chunk(F, params, keys, step0, nsteps) -> F
      F      (B, nf_max, N, N) device array            [donated]
      params dict of device arrays (packing) + "E" (precompute_E)
             or "D"(B,nf) + "k2"(N,N//2+1)             (on-the-fly)
      keys   (B, 2) uint32 per-world PRNG keys (batch_keys)
      step0  int32 absolute step index of F            [traced]
      nsteps int                                       [static]
    """
    jax, jnp = _jax()                             # [blobkit edit E18]
    HI = jax.lax.Precision.HIGHEST
    na = struct["na_max"]
    tanh_slots = tuple(struct["tanh_slots"])
    nb = struct["nb_max"] if struct["has_bilin"] else 0
    use_noise = noise > 0.0
    nsig64 = float(noise) * float(np.sqrt(dt))

    def reaction(F, p):
        U = F[:, :na]
        X = F[:, na:]
        Z = U - p["u0"][:, :, None, None]
        RU = (p["lam"][:, :, None, None] * U - U ** 3
              + p["k1"][:, :, None, None]
              - jnp.einsum("bic,bcyx->biyx", p["K"], X, precision=HI))
        for k in range(nb):
            idx_c = p["bi_c"][:, k][:, None, None, None]
            idx_c2 = p["bi_c2"][:, k][:, None, None, None]
            xc = jnp.take_along_axis(X, idx_c, axis=1)[:, 0]
            xc2 = jnp.take_along_axis(X, idx_c2, axis=1)[:, 0]
            oh = jax.nn.one_hot(p["bi_i"][:, k], na, dtype=F.dtype)  # (B, na)
            RU = RU - (p["bi_coef"][:, k][:, None] * oh)[:, :, None, None] \
                      * (xc * xc2)[:, None]
        drive = jnp.einsum("bca,bayx->bcyx", p["Wid"], Z, precision=HI)
        for c in tanh_slots:
            tz = jnp.tanh(jnp.clip(Z - p["thr"][:, c][:, None, None, None],
                                   0.0, None)
                          / p["sc"][:, c][:, None, None, None])
            drive = drive.at[:, c].add(
                jnp.einsum("ba,bayx->byx", p["Wtanh"][:, c], tz, precision=HI))
        RX = (drive - X) * p["inv_tau"][:, :, None, None]
        return jnp.concatenate([RU, RX], axis=1)

    def diffuse(F, p):
        Fh = jnp.fft.rfft2(F)
        if precompute_E:
            Fh = Fh * p["E"]
        else:
            E = jnp.exp(-p["D"][:, :, None, None] * p["k2"][None, None] * dt
                        ).astype(F.dtype)
            Fh = Fh * E
        return jnp.fft.irfft2(Fh, s=(N, N))

    def body_factory(params, keys):
        def body(i, F):
            R = reaction(F, params)
            if unfused:                    # bench-only: force R to materialize
                R = jax.lax.optimization_barrier(R)
            F = F + jnp.asarray(dt, F.dtype) * R
            if use_noise:
                # key layout: fold (step, field) into each world key so a
                # world's noise stream is independent of batch shape/padding
                kk = jax.vmap(lambda k: jax.random.fold_in(k, i))(keys)
                def world_noise(k):
                    def field_noise(a):
                        return jax.random.normal(jax.random.fold_in(k, a),
                                                 (N, N), dtype=F.dtype)
                    return jax.vmap(field_noise)(jnp.arange(na))
                xi = jax.vmap(world_noise)(kk)
                F = F.at[:, :na].add(jnp.asarray(nsig64, F.dtype)
                                     * params["act_mask"][:, :, None, None] * xi)
            return diffuse(F, params)
        return body

    @partial(jax.jit, static_argnums=(4,), donate_argnums=(0,))
    def step_chunk(F, params, keys, step0, nsteps):
        body = body_factory(params, keys)
        return jax.lax.fori_loop(step0, step0 + nsteps, body, F)

    return step_chunk


def make_single_step(struct, N, dx, dt, noise=0.0, donate=True):
    """One jitted step (python-loop mode; bench baseline for launch overhead).
    Same math as make_stepper with nsteps=1, but without the fori_loop."""
    chunk = make_stepper(struct, N, dx, dt, noise=noise)

    def step(F, params, keys, step0):
        return chunk(F, params, keys, step0, 1)

    return step


# ==================================================== [packing.py verbatim]



def pack_genomes(genomes, dtype=np.float32):
    """-> (params: dict of np arrays, struct: dict of static ints/tuples).
    params keys: lam,k1,u0,act_mask (B,na) | K (B,na,nc) | Wid,Wtanh (B,nc,na)
    | thr,sc,inv_tau,chan_mask (B,nc) | D (B,nf) | bi_i,bi_c,bi_c2,bi_coef (B,nb)
    | thr_a, thr_lo (B,na) f64 tracking thresholds (not used on device).
    """
    B = len(genomes)
    na_max = max(len(g["acts"]) for g in genomes)
    nc_max = max(len(g["chans"]) for g in genomes)
    nb_max = max((len(g.get("bilin", [])) for g in genomes), default=0)
    nf_max = na_max + nc_max

    lam = np.zeros((B, na_max)); k1 = np.zeros((B, na_max))
    u0 = np.zeros((B, na_max)); act_mask = np.zeros((B, na_max))
    K = np.zeros((B, na_max, nc_max))
    Wid = np.zeros((B, nc_max, na_max)); Wtanh = np.zeros((B, nc_max, na_max))
    thr = np.zeros((B, nc_max)); sc = np.ones((B, nc_max))
    inv_tau = np.zeros((B, nc_max)); chan_mask = np.zeros((B, nc_max))
    D = np.zeros((B, nf_max))
    nbm = max(nb_max, 1)
    bi_i = np.zeros((B, nbm), np.int32); bi_c = np.zeros((B, nbm), np.int32)
    bi_c2 = np.zeros((B, nbm), np.int32); bi_coef = np.zeros((B, nbm))
    thr_a = np.zeros((B, na_max)); thr_lo = np.zeros((B, na_max))
    tanh_slots = set()

    for b, g in enumerate(genomes):
        na, nc = len(g["acts"]), len(g["chans"])
        Wg = np.asarray(g["W"], float); Kg = np.asarray(g["K"], float)
        for i, a in enumerate(g["acts"]):
            lam[b, i] = a["lam"]; k1[b, i] = a["k1"]; u0[b, i] = a["u0"]
            act_mask[b, i] = 1.0
            D[b, i] = a["Du"]
            s = np.sqrt(max(a["lam"], 1e-9))
            thr_a[b, i] = a["u0"] + 0.45 * (s - a["u0"])
            thr_lo[b, i] = a["u0"] + 0.30 * (s - a["u0"])
        K[b, :na, :nc] = Kg
        for c, ch in enumerate(g["chans"]):
            inv_tau[b, c] = 1.0 / ch["tau"]
            chan_mask[b, c] = 1.0
            D[b, na_max + c] = ch["D"]
            thr[b, c] = ch.get("thr", 0.0); sc[b, c] = ch.get("sc", 1.0)
            if ch["g"] == "id":
                Wid[b, c, :na] = Wg[c]
            else:
                Wtanh[b, c, :na] = Wg[c]
                tanh_slots.add(c)
        for k, (i, c, c2, coef) in enumerate(g.get("bilin", [])):
            bi_i[b, k] = i; bi_c[b, k] = c; bi_c2[b, k] = c2; bi_coef[b, k] = coef

    f = lambda a: a.astype(dtype)
    params = dict(lam=f(lam), k1=f(k1), u0=f(u0), act_mask=f(act_mask),
                  K=f(K), Wid=f(Wid), Wtanh=f(Wtanh), thr=f(thr), sc=f(sc),
                  inv_tau=f(inv_tau), chan_mask=f(chan_mask), D=D,
                  bi_i=bi_i, bi_c=bi_c, bi_c2=bi_c2, bi_coef=f(bi_coef))
    struct = dict(B=B, na_max=na_max, nc_max=nc_max, nb_max=nb_max,
                  nf_max=nf_max, tanh_slots=tuple(sorted(tanh_slots)),
                  has_bilin=bool(nb_max > 0))
    aux = dict(thr_a=thr_a, thr_lo=thr_lo)
    return params, struct, aux


def pack_states(genomes, states, na_max=None, nc_max=None):
    """Stack per-world (na_i+nc_i, N, N) states into (B, nf_max, N, N), padding
    activator block and channel block separately (channels start at na_max)."""
    B = len(genomes)
    na_max = na_max or max(len(g["acts"]) for g in genomes)
    nc_max = nc_max or max(len(g["chans"]) for g in genomes)
    N = states[0].shape[-1]
    F = np.zeros((B, na_max + nc_max, N, N), states[0].dtype)
    for b, (g, s) in enumerate(zip(genomes, states)):
        na, nc = len(g["acts"]), len(g["chans"])
        F[b, :na] = s[:na]
        F[b, na_max:na_max + nc] = s[na:na + nc]
    return F


def unpack_state(g, Fb, na_max):
    """(nf_max, N, N) padded world state -> (na+nc, N, N) natural layout."""
    na, nc = len(g["acts"]), len(g["chans"])
    return np.concatenate([Fb[:na], Fb[na_max:na_max + nc]], axis=0)


# ======================================================= [soup.py verbatim]

import os, time

from . import sim_cpu as V2                    # locked CPU assay [blobkit edit E20]
from . import driver as DRV                    # 0.2 shared sim driver [blobkit 0.2 E23]
from .sim_v1 import NOISE, N_SOUP


# ------------------------------------------------------------- single world
def init_soup_gpu(g, L=128.0, seed=0, n_soup=N_SOUP, dtype="f32", kicks=None,
                  noise=NOISE, gpu_seed=None):
    """soup_sim_v2.init_soup + device packing. gpu_seed defaults to seed."""
    if dtype not in ("f32", "f64"):
        raise ValueError("dtype must be f32 or f64")
    S = V2.init_soup(g, L=L, seed=seed, n_soup=n_soup, dtype=dtype,
                     kicks=kicks, noise=noise, workers=0)
    _attach_gpu(S, [g], [S["F"]], [seed if gpu_seed is None else gpu_seed],
                dtype, noise)
    return S


def _attach_gpu(S_master, gens, states, gpu_seeds, dtype, noise):
    _, jnp = _jax()                               # [blobkit edit E21]
    npdt = np.float32 if dtype == "f32" else np.float64
    if npdt is np.float64:
        enable_x64()          # must precede device-array creation (JAX trap:
                              # without x64, f64 inputs silently become f32)
    N = states[0].shape[-1]
    dx, dt = 0.5, 0.02
    params, struct, aux = pack_genomes(gens, dtype=npdt)
    Fb = pack_states(gens, [np.asarray(s, npdt) for s in states],
                     struct["na_max"], struct["nc_max"])
    p = {k: jnp.asarray(v) for k, v in params.items()}
    p["E"] = diffusion_E(params["D"], N, dx, dt, npdt)
    G = dict(params=p, struct=struct,
             step=make_stepper(struct, N, dx, dt, noise=noise),
             keys=batch_keys(gpu_seeds), F=jnp.asarray(Fb),
             gens=gens, N=N)
    S_master["_gpu"] = G
    return G


def _pull(G, acts_only=False):
    """Device -> host, per-world natural layout list. Blocks.
    acts_only: pull just the activator block (tracking records need only u;
    4x less PCIe traffic + f64 conversion). Channel slots are filled with 0."""
    na_max = G["struct"]["na_max"]
    if acts_only:
        Fh = np.asarray(G["F"][:, :na_max])
        out = []
        for b, g in enumerate(G["gens"]):
            na, nc = len(g["acts"]), len(g["chans"])
            s = np.zeros((na + nc,) + Fh.shape[-2:], Fh.dtype)
            s[:na] = Fh[b, :na]
            out.append(s)
        return out
    Fh = np.asarray(G["F"])
    return [unpack_state(g, Fh[b], na_max)
            for b, g in enumerate(G["gens"])]


def _record_host(S, Fh, t_now):
    """0.2 record seam: host-side record via the verbatim locked V2._record.
    Contract for driver.run_chunks record_fn; a 0.3 device-side reduction
    variant plugs in here without touching the driver. [blobkit 0.2 E23]"""
    S["F"] = Fh
    ok = V2._record(S, t_now)
    S["recorded_at"] = t_now
    if not ok:
        S["_t_stopped"] = t_now            # CPU contract: stop at exit point


def _driver_kw(S, G):
    """Shared plumbing: bind this batch's step/pull to driver kwargs.
    [blobkit 0.2 E23]"""
    def step_fn(t, n):
        G["F"] = G["step"](G["F"], G["params"], G["keys"], t, n)

    def pull_fn(full):
        return _pull(G, acts_only=not full)

    return dict(step_fn=step_fn, pull_fn=pull_fn, record_fn=_record_host,
                rec=S["rec"], crec=S["crec"], dt=S["dt"])


def advance_gpu(S, T_target):
    """GPU version of soup_sim_v2.advance. Same record grid, same exits.
    Since 0.2 the chunk loop lives in driver.run_chunks (G2-gated identity).
    [blobkit 0.2 E23]"""
    dt = S["dt"]
    steps_target = int(round(T_target / dt))
    if steps_target % S["crec"] != 0:
        raise ValueError("T_target must be a multiple of CREC")
    G = S["_gpu"]
    DRV.run_chunks([S], steps_target, overlap=False, stop_when_dead=True,
                   **_driver_kw(S, G))
    return S["status"]


def snapshot_rec_gpu(S):
    return V2.snapshot_rec(S)


# ------------------------------------------------------------- batched pop
def init_soup_gpu_batch(jobs, L=128.0, dtype="f32", noise=NOISE, kicks_map=None,
                        ics=None):
    """jobs: list of (genome, seed). One padded tensor for the whole batch.
    Returns SS = dict(worlds=[S...], _gpu=...). Each S is a full v2 state dict
    (independent records); stepping is shared.
    ics: optional list aligned with jobs; entry i (if not None) is an
    (na+nc, N, N) array replacing lane i's soup IC after init_soup — the
    documented data-level hook on S["F"] (same semantics as
    assay_v3.run_assay(ic_override=); applied before device packing)."""
    jobs = list(jobs)
    if not jobs:
        raise ValueError("jobs must contain at least one world")
    if dtype not in ("f32", "f64"):
        raise ValueError("dtype must be f32 or f64")
    if ics is not None and len(ics) != len(jobs):
        raise ValueError("ics must have exactly one entry per job (use None for defaults)")
    worlds, gens, states, seeds = [], [], [], []
    for i, (g, seed) in enumerate(jobs):
        kicks = (kicks_map or {}).get(g.get("id"))
        S = V2.init_soup(g, L=L, seed=seed, dtype=dtype, kicks=kicks,
                         noise=noise, workers=0)
        ic = ics[i] if ics is not None else None
        if ic is not None:
            ic = np.asarray(ic)
            if ic.shape != S["F"].shape:
                raise ValueError(f"lane {i} ic shape {ic.shape} != state "
                                 f"shape {S['F'].shape}")
            if ic.dtype.kind not in "fiu" or not np.isfinite(ic).all():
                raise ValueError(f"lane {i} ic must contain finite real numbers")
            S["F"] = ic.astype(S["F"].dtype)
            if not np.isfinite(S["F"]).all():
                raise ValueError(f"lane {i} ic exceeds the {dtype} range")
        worlds.append(S); gens.append(g); states.append(S["F"]); seeds.append(seed)
    master = dict(worlds=worlds)
    G = _attach_gpu(master, gens, states, seeds, dtype, noise)
    for S in worlds:
        S["_gpu"] = G          # shared handle (advance via the batch driver)
    return master


def advance_gpu_batch(SS, T_target, overlap=True, progress=None):
    """Advance all worlds to T_target on one tensor. CPU tracking overlaps the
    next GPU chunk (JAX async dispatch). Worlds whose status != ok stop being
    recorded but keep stepping (padding-inert, no cross-talk).
    Since 0.2 the chunk loop lives in driver.run_chunks (G2-gated identity).
    [blobkit 0.2 E23]"""
    worlds = SS["worlds"]
    G = worlds[0]["_gpu"]
    steps_target = int(round(T_target / worlds[0]["dt"]))
    if steps_target % worlds[0]["crec"] != 0:
        raise ValueError("T_target must be a multiple of CREC")

    from concurrent.futures import ThreadPoolExecutor
    n_rec_threads = int(os.environ.get("BLOBGPU_REC_THREADS",
                                       min(16, os.cpu_count() or 1)))
    ex = (ThreadPoolExecutor(n_rec_threads)
          if (n_rec_threads > 1 and len(worlds) > 4) else None)
    try:
        return DRV.run_chunks(worlds, steps_target, overlap=overlap,
                              stop_when_dead=False, rec_pool=ex,
                              progress=progress,
                              **_driver_kw(worlds[0], G))
    finally:
        if ex is not None:
            ex.shutdown(wait=True)


# ------------------------------------------------------------- run_soup_gpu
def run_soup_gpu(g, L=128.0, T=5000.0, seed=0, n_soup=N_SOUP, dtype="f32",
                 kicks=None, noise=NOISE, chunk_tu=None):
    """Drop-in for soup_sim.run_soup / the v2 init+advance+snapshot pipeline:
    same record dict keys (v2 superset), same protocol, GPU stepping.
    chunk_tu: optional intermediate advance targets (multiples of CREC)."""
    S = init_soup_gpu(g, L=L, seed=seed, n_soup=n_soup, dtype=dtype,
                      kicks=kicks, noise=noise)
    S["snap_t"] = sorted({0.0, 250.0, T / 2, float(T)})
    targets = list(np.arange(chunk_tu, T + 1e-9, chunk_tu)) if chunk_tu else [T]
    for Tt in targets:
        if advance_gpu(S, float(Tt)) != "ok":
            break
    return snapshot_rec_gpu(S)
