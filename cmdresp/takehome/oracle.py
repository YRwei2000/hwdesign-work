"""Independent vectorized NumPy pooling reference, including first-tie bit selection.

No import from pool.py, no model/parser calls. Inputs must satisfy the spec.
"""
import numpy as np

def reference(matrix, k):
    a = np.asarray(matrix, dtype=np.float32)
    h, w = a.shape
    blocks = a.reshape(h//k, k, w//k, k)
    maxima = blocks.max(axis=(1,3))
    windows = blocks.transpose(0,2,1,3).reshape(h//k,w//k,k*k)
    # np.max's zero-sign tie is not specified by the project. Gather original bits
    # at the first equal value, independently of the scalar model's scan.
    first = (windows == maxima[...,None]).argmax(axis=2)
    raw = np.take_along_axis(windows.view(np.uint32), first[...,None], axis=2)[...,0]
    return raw.view(np.float32)
