import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

D = np.load("data/raw/edge_evidence.npz", allow_pickle=True)
wid, lon, lat = D["wid"], D["lon"], D["lat"]
isb, inside, assess = D["bridge"], D["inside"], D["assess"]
ev, pl = D["ev"], D["pl"]
NEW = ["y25_0721", "y25_0802", "y25_0814", "y25_0826", "y24_0714",
       "y24_0726", "y24_0807", "y24_0819", "y24_0831"]
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
base = isb & inside & assess
print("assessable bridge edges:", int(base.sum()), "| bridge ways:", len(np.unique(wid[base])),
      "| bridge structures:", None)


def n_structures(mask):
    idx = np.nonzero(mask)[0]
    n = len(idx)
    if n == 0:
        return 0
    pts = np.stack([lon[idx] * KX, lat[idx] * KY], axis=1)
    pairs = cKDTree(pts).query_pairs(150.0, output_type="ndarray")
    if len(pairs) == 0:
        return n
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    return int(connected_components(g, directed=False)[0])


def report(name, score, others):
    k = (others >= score).sum(axis=0)
    hit = base & (score >= 0.05)
    flag = hit & (k == 0)
    print(name, "| ways with score>=0.05:", len(np.unique(wid[hit])),
          "| flagged ways:", len(np.unique(wid[flag])),
          "| flagged structures:", n_structures(flag))


print("all assessable bridge structures:", n_structures(base))
report("EVENT", ev, pl)
for i, t in enumerate(NEW):
    report(t, pl[i], np.delete(pl, i, axis=0))