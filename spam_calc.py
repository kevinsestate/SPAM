"""
SPAM Transmission Matrix Calculations

Port of MATLAB functions for computing transmission matrices from material
parameters and SPAM S-parameter measurements.  Reference document:
"Transmission Matrix Formulation for Anisotropic Slabs" (PDF).

Public API
----------
solve_dispersion    -- Solve dispersion relation for anisotropic slab modes
material_to_tmatrix -- Forward model: material tensors → theoretical T-matrix
spam_s_to_tmatrix   -- Measurement path: SPAM S-parameters → measured T-matrix
tmatrix_error       -- Relative RMS error between two T-matrices
compute_k0d         -- Helper: frequency + thickness → k0*d product
mil_to_m            -- Helper: mil → metre conversion
"""

import numpy as np

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
C0 = 299_792_458.0            # speed of light  [m/s]
EP0 = 8.854_187_817e-12       # vacuum permittivity  [F/m]
MU0 = 1.0 / (C0**2 * EP0)    # vacuum permeability  [H/m]
ETA0 = np.sqrt(MU0 / EP0)    # free-space impedance [Ω]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def compute_k0d(f_hz, d_m):
    """Return the free-space-wavenumber × thickness product.

    Parameters
    ----------
    f_hz : float
        Operating frequency in Hz.
    d_m : float
        Slab thickness in metres.

    Returns
    -------
    float
    """
    lam0 = C0 / f_hz
    k0 = 2.0 * np.pi / lam0
    return k0 * d_m


def mil_to_m(d_mil):
    """Convert thickness from mils to metres (1 mil = 0.001 inch)."""
    return d_mil / 39.37 * 1e-3


# ---------------------------------------------------------------------------
# Internal: shared tensor + dispersion computation
# ---------------------------------------------------------------------------
def _dispersion_internals(erv, mrv, theta_deg):
    """Build tensors, compute sigmas, polynomial coefficients, roots, and G.

    This is the shared core used by both ``solve_dispersion`` and
    ``material_to_tmatrix``.

    Parameters
    ----------
    erv : array-like, length 6
        [eps_xx, eps_xy, eps_xz, eps_yy, eps_yz, eps_zz]
    mrv : array-like, length 6
        [mu_xx,  mu_xy,  mu_xz,  mu_yy,  mu_yz,  mu_zz]
    theta_deg : array-like
        Incidence angles in degrees.

    Returns
    -------
    dict  with keys:
        pz, px, Ntheta, Gxx, Gxy, Gyx, Gyy,
        e_x, e_xy, e_zx, e_y, e_yz, e_z,
        m_x, m_xy, m_zx, m_y, m_yz, m_z
    """
    erv = np.asarray(erv, dtype=complex)
    mrv = np.asarray(mrv, dtype=complex)
    theta_deg = np.asarray(theta_deg, dtype=float).ravel()

    # -- symmetric 3×3 tensors --
    epr = np.array([[erv[0], erv[1], erv[2]],
                    [erv[1], erv[3], erv[4]],
                    [erv[2], erv[4], erv[5]]])
    mur = np.array([[mrv[0], mrv[1], mrv[2]],
                    [mrv[1], mrv[3], mrv[4]],
                    [mrv[2], mrv[4], mrv[5]]])

    e = np.linalg.inv(epr)
    m = np.linalg.inv(mur)

    e_x  = e[0, 0]; e_xy = e[0, 1]; e_zx = e[0, 2]
    e_y  = e[1, 1]; e_yz = e[1, 2]
    e_z  = e[2, 2]
    m_x  = m[0, 0]; m_xy = m[0, 1]; m_zx = m[0, 2]
    m_y  = m[1, 1]; m_yz = m[1, 2]
    m_z  = m[2, 2]

    Ntheta = len(theta_deg)
    px_1d = np.sin(np.deg2rad(theta_deg))          # shape (Ntheta,)

    # -- 12 sigma helper terms (PDF §1) --
    s1  = e_xy * m_xy - e_x  * m_y
    s2  = 2 * e_zx * m_y - e_yz * m_xy - e_xy * m_yz
    s3  = e_yz * m_yz - e_z  * m_y
    s4  = e_y  * m_xy - e_xy * m_y
    s5  = e_yz * m_y  - e_y  * m_yz
    s6  = e_x  * m_xy - m_x  * e_xy
    s7  = (e_yz * m_x - e_x * m_yz
           + 2 * e_xy * m_zx - 2 * e_zx * m_xy)
    s8  = (e_z * m_xy - e_xy * m_z
           - 2 * e_yz * m_zx + 2 * e_zx * m_yz)
    s9  = e_yz * m_z  - e_z  * m_yz
    s10 = e_xy * m_xy - e_y  * m_x
    s11 = 2 * e_y * m_zx - e_yz * m_xy - e_xy * m_yz
    s12 = e_yz * m_yz - e_y  * m_z

    # -- polynomial coefficients A0..A4  (PDF eq 0.7 / 0.8) --
    px = px_1d
    A0 = (s3 * s12 - s5 * s9) * px**4 + (s3 + s12) * px**2 + 1
    A1 = ((s2 * s12 - s5 * s8 - s4 * s9 + s3 * s11) * px**3
          + (s2 + s11) * px)
    A2 = ((s1 * s12 - s5 * s7 - s4 * s8 + s2 * s11 + s3 * s10) * px**2
          + s1 + s10)
    A3 = (s1 * s11 - s5 * s6 - s4 * s7 + s2 * s10) * px
    A4 = np.full_like(px, s1 * s10 - s4 * s6, dtype=complex)

    # -- solve 4th-order dispersion equation (batched companion eigvals) --
    inv_A4 = 1.0 / A4
    C = np.zeros((Ntheta, 4, 4), dtype=complex)
    C[:, 0, 0] = -A3 * inv_A4
    C[:, 0, 1] = -A2 * inv_A4
    C[:, 0, 2] = -A1 * inv_A4
    C[:, 0, 3] = -A0 * inv_A4
    C[:, 1, 0] = 1.0
    C[:, 2, 1] = 1.0
    C[:, 3, 2] = 1.0
    pz = np.linalg.eigvals(C)

    # -- G-matrix components  (Ntheta × 4)  (PDF eqs 0.3–0.6) --
    px = px_1d[:, np.newaxis]                       # (Ntheta, 1)
    Gxx = s1 * pz**2 + s2 * px * pz + s3 * px**2
    Gxy = s4 * pz**2 + s5 * px * pz
    Gyx = (1.0 / pz) * (s6 * pz**3 + s7 * px * pz**2
                         + s8 * px**2 * pz + s9 * px**3)
    Gyy = s10 * pz**2 + s11 * px * pz + s12 * px**2

    return dict(
        pz=pz, px=px, Ntheta=Ntheta,
        Gxx=Gxx, Gxy=Gxy, Gyx=Gyx, Gyy=Gyy,
        e_x=e_x, e_xy=e_xy, e_zx=e_zx,
        e_y=e_y, e_yz=e_yz, e_z=e_z,
        m_x=m_x, m_xy=m_xy, m_zx=m_zx,
        m_y=m_y, m_yz=m_yz, m_z=m_z,
    )


# ---------------------------------------------------------------------------
# Public: dispersion solver  (port of f_solve_dispersion.m)
# ---------------------------------------------------------------------------
def solve_dispersion(erv, mrv, theta_deg):
    """Solve the dispersion relation for an anisotropic slab.

    Parameters
    ----------
    erv : array-like, length 6
        Relative permittivity tensor components
        [eps_xx, eps_xy, eps_xz, eps_yy, eps_yz, eps_zz].
    mrv : array-like, length 6
        Relative permeability tensor components
        [mu_xx, mu_xy, mu_xz, mu_yy, mu_yz, mu_zz].
    theta_deg : array-like
        Incidence angles in degrees.

    Returns
    -------
    Gxx, Gxy, Gyx, Gyy : ndarray, shape (Ntheta, 4)
        Dispersion-matrix components for each mode at each angle.
    pz : ndarray, shape (Ntheta, 4)
        Normalised z-component of propagation vector for each mode.
    """
    d = _dispersion_internals(erv, mrv, theta_deg)
    return d['Gxx'], d['Gxy'], d['Gyx'], d['Gyy'], d['pz']


# ---------------------------------------------------------------------------
# Public: forward model  (port of f_mater2abcd.m)
# ---------------------------------------------------------------------------
def material_to_tmatrix(erv, mrv, theta_deg, k0d):
    """Compute the normalised transmission matrix from material parameters.

    This is the *forward model*: given material tensors, predict what the
    T-matrix should look like at every incidence angle.

    Parameters
    ----------
    erv : array-like, length 6
        Relative permittivity tensor components.
    mrv : array-like, length 6
        Relative permeability tensor components.
    theta_deg : array-like
        Incidence angles in degrees.
    k0d : float
        Free-space wavenumber × slab thickness.

    Returns
    -------
    T : ndarray, shape (Ntheta, 4, 4)
        Normalised transmission (ABCD) matrix at each angle.
    """
    d = _dispersion_internals(erv, mrv, theta_deg)
    pz      = d['pz']          # (Ntheta, 4)
    px      = d['px']          # (Ntheta, 1)
    Ntheta  = d['Ntheta']
    Gxx     = d['Gxx']
    Gxy     = d['Gxy']
    Gyx     = d['Gyx']
    Gyy     = d['Gyy']
    e_x     = d['e_x'];  e_xy = d['e_xy']; e_zx = d['e_zx']
    e_y     = d['e_y'];  e_yz = d['e_yz']; e_z  = d['e_z']
    m_x     = d['m_x'];  m_xy = d['m_xy']; m_zx = d['m_zx']
    m_y     = d['m_y'];  m_yz = d['m_yz']

    # -- eigenvectors  (PDF §4, eqs 0.49–0.52) --
    EDx = Gyy - Gxy + 1                                      # (Ntheta, 4)
    EDy = Gxx - Gyx + 1

    Ex = (e_x - px / pz * e_zx) * EDx + e_xy * EDy
    Ey = (e_xy - px / pz * e_yz) * EDx + e_y  * EDy

    c0Bx = (px * e_yz - pz * e_xy) * EDx - pz * e_y * EDy
    c0By = ((pz * e_x - px * e_zx
             + px / pz * (px * e_z - pz * e_zx)) * EDx
            + (pz * e_xy - px * e_yz) * EDy)

    eta0Jx = (m_xy - px / pz * m_yz) * c0Bx + m_y  * c0By
    eta0Jy = (px / pz * m_zx - m_x)  * c0Bx - m_xy * c0By

    # -- assemble V, Λ, and T = V·Λ·V⁻¹  (fully vectorised) --
    V = np.stack([Ex, Ey, eta0Jx, eta0Jy], axis=1)   # (Ntheta, 4, 4)

    # normalise each column by its largest-magnitude entry
    max_idx = np.argmax(np.abs(V), axis=1)             # (Ntheta, 4)
    ti_idx = np.arange(Ntheta)[:, np.newaxis]
    mode_idx = np.arange(4)[np.newaxis, :]
    max_vals = V[ti_idx, max_idx, mode_idx]             # (Ntheta, 4)
    V = V / max_vals[:, np.newaxis, :]

    # V @ diag(exp) = column-wise multiply
    phase = np.exp(1j * k0d * pz)                      # (Ntheta, 4)
    VL = V * phase[:, np.newaxis, :]                    # (Ntheta, 4, 4)

    try:
        T = VL @ np.linalg.inv(V)
    except np.linalg.LinAlgError:
        Vinv = np.empty_like(V)
        for ti in range(Ntheta):
            try:
                Vinv[ti] = np.linalg.inv(V[ti])
            except np.linalg.LinAlgError:
                Vinv[ti] = np.linalg.pinv(V[ti])
        T = VL @ Vinv

    return T


# ---------------------------------------------------------------------------
# Public: measurement path  (port of f_spams2abcd.m)
# ---------------------------------------------------------------------------
def spam_s_to_tmatrix(S_SPAM, theta_deg):
    """Convert SPAM S-parameters to a normalised transmission matrix.

    Parameters
    ----------
    S_SPAM : ndarray, shape (Ntheta, 4, 4)
        SPAM scattering matrix in h-v coordinates at each angle.
    theta_deg : array-like
        Incidence angles in degrees.

    Returns
    -------
    T : ndarray, shape (Ntheta, 4, 4)
        Normalised transmission (ABCD) matrix at each angle.
    """
    theta_deg = np.asarray(theta_deg, dtype=float).ravel()
    S_SPAM = np.asarray(S_SPAM, dtype=complex)
    Ntheta = len(theta_deg)

    ct = np.cos(np.deg2rad(theta_deg))                # (Ntheta,)
    st = 1.0 / ct
    ones = np.ones(Ntheta, dtype=complex)

    # Row/column scaling replaces diagonal-matrix multiplies
    hv2xy = np.stack([ct, ones, ct, ones], axis=1)     # (Ntheta, 4)
    xy2hv = np.stack([st, ones, st, ones], axis=1)
    S_XY = hv2xy[:, :, np.newaxis] * S_SPAM * xy2hv[:, np.newaxis, :]

    s11 = S_XY[:, 0:2, 0:2]
    s21 = S_XY[:, 2:4, 0:2]
    s12 = S_XY[:, 0:2, 2:4]
    s22 = S_XY[:, 2:4, 2:4]

    I2 = np.eye(2, dtype=complex)
    top = np.zeros((Ntheta, 4, 4), dtype=complex)
    top[:, 0:2, 0:2] = I2 + s11
    top[:, 0:2, 2:4] = s12
    top[:, 2:4, 0:2] = I2 - s11
    top[:, 2:4, 2:4] = -s12

    bot = np.zeros((Ntheta, 4, 4), dtype=complex)
    bot[:, 0:2, 0:2] = s21
    bot[:, 0:2, 2:4] = I2 + s22
    bot[:, 2:4, 0:2] = s21
    bot[:, 2:4, 2:4] = -I2 + s22

    M = top @ np.linalg.inv(bot)                       # (Ntheta, 4, 4)

    yy = np.stack([ones, ones, st, ct], axis=1)
    zz = np.stack([ones, ones, ct, st], axis=1)
    T = yy[:, :, np.newaxis] * M * zz[:, np.newaxis, :]

    return T


# ---------------------------------------------------------------------------
# Public: error metric  (port of f_errT.m)
# ---------------------------------------------------------------------------
def tmatrix_error(T_ref, T_comp):
    """Relative RMS error between two T-matrix stacks.

    Parameters
    ----------
    T_ref : ndarray, shape (Ntheta, 4, 4)
        Reference transmission matrix.
    T_comp : ndarray, shape (Ntheta, 4, 4)
        Comparison transmission matrix.

    Returns
    -------
    err_per_angle : ndarray, shape (Ntheta,)
        Relative error at each angle.
    err_total : float
        Mean relative error across all angles.
    """
    diff = T_ref - T_comp
    num = np.sum(np.abs(diff)**2, axis=(1, 2))
    den = np.sum(np.abs(T_ref)**2, axis=(1, 2))
    err = np.sqrt(num / den)
    return err, float(np.mean(err))
