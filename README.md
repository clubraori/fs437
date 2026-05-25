# fs437 — five days of a living mind

A [Tentatively725](https://tentatively725.com) experiment.

A 3D sound-room and explainer built from 2.6M spike events recorded over ~118 hours from FinalSpark organoid **fs437**, a stem-cell-derived brain organoid sitting on a 32-electrode multi-electrode array in Vevey, Switzerland.

**Live:** [pakrasi.github.io/fs437](https://pakrasi.github.io/fs437)

## What it is

Two modes, toggled by a top-right pill (`listen · read`):

- **listen** — A 3D room with the 32 electrodes in their physical 4 × 8 layout. The full 5-day recording plays back at 60× speed (1 hour = 1 minute), each spike becoming a brief visual pulse and a pitched audio click. Two views: top-down (equal-volume mix) and float (mouse-drag orbit, spatial audio).
- **read** — A five-section scrolling essay walking through the same data analytically: *Rhythm → Voices → Geography → Crescendo → Shape.*

## Data

Source: [FinalSpark](https://finalspark.com/) Neuroplatform. Raw CSV is ~128 MB and is **not committed** — see `src/preprocess.py` for the transform pipeline.

The preprocessor emits:
- `docs/data/fs437_spikes.bin` (~15.6 MB) — compact binary spike log used by the room
- `docs/data/fs437_summary.json` (~1 MB) — per-minute aggregates used by the explainer

## Repo layout

```
fs437/
├── docs/                       # GitHub Pages root
│   ├── index.html              # the full piece
│   └── data/
│       ├── fs437_spikes.bin    # generated, ~15.6 MB
│       └── fs437_summary.json  # generated, ~1 MB
└── src/
    └── preprocess.py           # CSV → binary + summary JSON
```

## Regenerating data

```bash
# Put SpikeDataToShare_fs437data.csv at src/data/raw/SpikeDataToShare_fs437data.csv
python3 src/preprocess.py
```

## Credits

- Data: [FinalSpark](https://finalspark.com/) Neuroplatform, Vevey, CH
- Concept + build: [Ishaan Pakrasi](https://tentatively725.com) for Tentatively725
- Sibling work: [Terrarium](https://pakrasi.github.io/tentatively725) — Rigetti Cepheus-1-108Q as a 3D ecosystem

## License

Code: MIT. Data: courtesy of FinalSpark — see their terms.
