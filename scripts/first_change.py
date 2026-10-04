import pathlib
import numpy as np
from scipy.ndimage import uniform_filter, shift as nd_shift
from skimage.registration import phase_cross_correlation
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path("data/raw")
pre = np.load(RAW / "pre_vv_window.npy").astype(np.float32)
post = np.load(RAW / "post_vv_window.npy").astype(np.float32)

h = min(pre.shape[0], post.shape[0])
w = min(pre.shape[1], post.shape[1])
pre, post = pre[:h, :w], post[:h, :w]
valid = (pre > 0) & (post > 0)
print("valid in both:", round(float(valid.mean()), 3))

for name, a in (("pre", pre), ("post", post)):
    v = a[a > 0]
    print(name, "DN p5/p50/p95:", np.percentile(v, [5, 50, 95]).round(1))


def to_db(a):
    return 20 * np.log10(np.clip(a, 1, None))


# coregistration offset from a central crop
cy, cx, s = h // 2, w // 2, 1024
a = to_db(pre)[cy - s:cy + s, cx - s:cx + s]
b = to_db(post)[cy - s:cy + s, cx - s:cx + s]
offset, err, _ = phase_cross_correlation(a - a.mean(), b - b.mean(), upsample_factor=10)
print("offset (rows, cols) applied to post:", offset, "error:", round(float(err), 3))
post_al = nd_shift(post, offset, order=1, mode="constant", cval=0)


def smooth_db(a, k=7):
    m = uniform_filter(a.astype(np.float32) ** 2, size=k)
    return 10 * np.log10(np.clip(m, 1, None))


diff = smooth_db(post_al) - smooth_db(pre)
valid = valid & (post_al > 0)
med = float(np.median(diff[valid]))
print("global offset removed (dB):", round(med, 2))
diff = diff - med
print("diff percentiles 1/5/50/95/99 (dB):", np.percentile(diff[valid], [1, 5, 50, 95, 99]).round(2))

np.save(RAW / "diff_db.npy", diff.astype(np.float32))
step = max(h // 1200, 1)
fig, ax = plt.subplots(1, 2, figsize=(14, 8), gridspec_kw={"width_ratios": [3, 1]})
ax[0].imshow(diff[::step, ::step], cmap="RdBu", vmin=-6, vmax=6)
ax[0].set_title("post minus pre (dB), raw pixel grid")
ax[0].axis("off")
ax[1].hist(diff[valid][::50], bins=100, range=(-10, 10))
ax[1].set_title("histogram")
plt.savefig(RAW / "first_change.png", dpi=110, bbox_inches="tight")