# Modern spatialdata stack on Python 3.12

Tutorials install the current `spatialdata` family (`spatialdata` 0.8.x,
`spatialdata-io` 0.7.x, `spatialdata-plot` 0.4.x, `squidpy` 1.8.x, `sopa` 2.2.x) rather
than the parent course's carefully-pinned `spatialdata==0.2.5.post0` /
`spatialdata-plot==0.2.6` / `numba==0.59.1` / Python 3.10 stack. Colab's runtime is
Python 3.12, which the old pins cannot run on, and `sopa` 2.x — required for the niche
Tutorial — needs `spatialdata>=0.7.3` anyway.

## Consequences

The four `spatialdata`-family versions must be bumped together; mixing majors across
them is the failure mode this pin set exists to prevent. Because the set is not
reproducible from a container, it is re-verified in real Colab shortly before the
Workshop, and the tested versions are recorded in `requirements-colab.txt`.
