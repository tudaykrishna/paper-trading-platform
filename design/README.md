# Design canvas

The UI was mocked up as a multi-artboard canvas before it was built. This folder
holds the canvas sources.

| File | What it is |
|---|---|
| `*.dc.html` | one artboard each (Login, Dashboard, Chart, Order Pad, the watchlist Rail component, the Style tile, …) |
| `canvas.json` | artboard layout, positions, sticky notes |
| `Logo.png` | the app logo — an origami paper boat on a rising trend line (transparent PNG) |
| `paper-trading-ui.html` | **generated** — the seeded, publishable canvas (git-ignored, ~2.5 MB) |

`paper-trading-ui.html` is regenerated from the sources and isn't committed. The
implemented app follows this design, with the accent colour now user-configurable
in **Settings**.
