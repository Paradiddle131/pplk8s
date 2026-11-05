# Vendored libraries

The report draws its charts with Observable Plot, which needs d3.
`build.py` inlines both files below into `index.html`, so the page stays one self-contained file, and refuses to build if a file's sha256 differs from the one listed here (it keeps the same list as `VENDOR`).
Each file is the unmodified UMD build from the package's npm tarball; its first line keeps the package's copyright header.

| Package | Version | File here | Path in the tarball | Source (npm tarball) | File sha256 |
| --- | --- | --- | --- | --- | --- |
| `d3` | 7.9.0 (published 2024-03-12) | `d3-7.9.0.min.js` | `package/dist/d3.min.js` | https://registry.npmjs.org/d3/-/d3-7.9.0.tgz | `f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539` |
| `@observablehq/plot` | 0.6.17 (published 2025-02-14) | `plot-0.6.17.umd.min.js` | `package/dist/plot.umd.min.js` | https://registry.npmjs.org/@observablehq/plot/-/plot-0.6.17.tgz | `4358086467740777dd788d6b27a95cebdbaefdd50c730a3060117073bd7134cb` |

Tarball checks, against the registry's `dist.integrity` (sha512), 2026-11-05:

| Tarball | sha512 (matches `dist.integrity`) | Tarball sha256 |
| --- | --- | --- |
| `d3-7.9.0.tgz` | `e1U46jVP+w7Iut8Jt8ri1YsPOvFpg46k+K8TpCb0P+zjCkjkPnV7WzfDJzMHy1LnA+wj5pLT1wjO901gLXeEhA==` | `7e36605710a2ba54846797c8c6d888911341b215ae53257dc32a49a0b824355e` |
| `plot-0.6.17.tgz` | `/qaXP/7mc4MUS0s4cPPFASDRjtsWp85/TbfsciqDgU1HwYixbSbbytNuInD8AcTYC3xaxACgVX06agdfQy9W+g==` | `4dcc9f7afd10caee8b2283c0075a5765610cfbbf6d7d93cdb153b3b5d3501afc` |

Newer releases exist (`d3` 7.9.1 and 7.9.2, Plot 0.6.18, all from 2026-11-03); they are less than two weeks old, so the pins stay on the versions above.

## Licences

Both packages are under the ISC licence; the full texts are `LICENSE-d3` (Copyright 2010-2023 Mike Bostock) and `LICENSE-plot` (Copyright 2020-2025 Observable, Inc.), copied from the same tarballs.
The inlined builds keep their one-line copyright headers.

## Updating

Download the new tarball from the registry, check its sha512 against `dist.integrity`, copy the UMD build here under a versioned name, then update the table above and `VENDOR` in `build.py`.
