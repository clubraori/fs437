"""Preprocess the fs437 CSV into two artifacts consumed by docs/index.html:

  1. docs/data/fs437_spikes.bin   (~15.6 MB)
       Compact binary log of every spike event. Used by the 3D room.

       Header (16 bytes):
         offset 0  : 8 bytes  magic "FS437\0\0\0"
         offset 8  : u32 LE   spike count
         offset 12 : u32 LE   t_start unix seconds (UTC)

       Body (N * 6 bytes, sorted ascending by time):
         offset 0  : u32 LE   dt_ms (ms since t_start)
         offset 4  : u8       electrode index (0..31)
         offset 5  : i8       amplitude scaled (-128..127 = -60..+60 µV)

  2. docs/data/fs437_summary.json (~1 MB)
       Per-minute aggregates, raw burst-window spikes, amplitude histogram.
       Used by the scrolling explainer's five sections.
"""

from __future__ import annotations

import csv
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CSV_PATH = HERE / "data" / "raw" / "SpikeDataToShare_fs437data.csv"
OUT_BIN = REPO / "docs" / "data" / "fs437_spikes.bin"
OUT_JSON = REPO / "docs" / "data" / "fs437_summary.json"

N_ELECTRODES = 32
BIN_SECONDS = 60
AMP_CLIP_UV = 60.0


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def main() -> None:
    if not CSV_PATH.exists():
        sys.exit(
            f"CSV not found at {CSV_PATH}\n"
            f"Put SpikeDataToShare_fs437data.csv at that path and re-run."
        )

    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)

    print(f"reading {CSV_PATH} ...", flush=True)

    # Pass 1: time bounds + row count
    t0: datetime | None = None
    t_last: datetime | None = None
    total_rows = 0
    with CSV_PATH.open() as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            ts = parse_ts(row[1])
            if t0 is None:
                t0 = ts
            t_last = ts
            total_rows += 1

    assert t0 is not None and t_last is not None
    span_seconds = (t_last - t0).total_seconds()
    n_bins = int(span_seconds // BIN_SECONDS) + 1
    t0_unix = int(t0.timestamp())

    print(f"  rows: {total_rows:,}")
    print(f"  span: {span_seconds/3600:.1f}h = {n_bins} bins")
    print(f"  t0:   {t0.isoformat()} (unix {t0_unix})")

    per_bin_per_ch = [[0] * N_ELECTRODES for _ in range(n_bins)]
    per_bin_total = [0] * n_bins
    per_ch_total = [0] * N_ELECTRODES
    amp_nbins = 24
    amp_hist = [0] * amp_nbins
    amp_hist_per_ch = [[0] * amp_nbins for _ in range(N_ELECTRODES)]

    # Pass 2: collect all spikes (CSV is grouped by electrode, NOT globally
    # sorted by time — we sort in memory after) + aggregate for summary JSON
    print(f"collecting spikes + aggregating ...", flush=True)

    spikes: list[tuple[int, int, int]] = []  # (dt_ms, ch, amp_i8)
    with CSV_PATH.open() as f_in:
        reader = csv.reader(f_in)
        next(reader)
        for row in reader:
            ts = parse_ts(row[1])
            amp = float(row[2])
            ch = int(row[3])
            if ch < 0 or ch >= N_ELECTRODES:
                continue

            dt_seconds = (ts - t0).total_seconds()
            dt_ms = int(dt_seconds * 1000)
            if dt_ms < 0:
                continue

            # bin aggregation
            b = int(dt_seconds // BIN_SECONDS)
            if 0 <= b < n_bins:
                per_bin_per_ch[b][ch] += 1
                per_bin_total[b] += 1
                per_ch_total[ch] += 1

            # amp histogram
            a_clamped = max(-AMP_CLIP_UV, min(AMP_CLIP_UV, amp))
            a_idx = int((a_clamped + AMP_CLIP_UV) / (2 * AMP_CLIP_UV) * amp_nbins)
            if a_idx == amp_nbins:
                a_idx -= 1
            amp_hist[a_idx] += 1
            amp_hist_per_ch[ch][a_idx] += 1

            # scale amplitude to int8: clip to [-60, 60] µV, scale to [-127, 127]
            amp_i8 = int(round(a_clamped / AMP_CLIP_UV * 127))
            amp_i8 = max(-128, min(127, amp_i8))

            spikes.append((dt_ms, ch, amp_i8))

    print(f"  collected {len(spikes):,} spikes; sorting globally by time ...", flush=True)
    spikes.sort(key=lambda s: s[0])

    print(f"writing {OUT_BIN} ...", flush=True)
    with OUT_BIN.open("wb") as f_out:
        f_out.write(b"FS437\0\0\0")
        f_out.write(struct.pack("<II", len(spikes), t0_unix))
        # Write in chunks to avoid building one giant bytes object
        CHUNK = 200_000
        for i in range(0, len(spikes), CHUNK):
            chunk = spikes[i : i + CHUNK]
            buf = b"".join(struct.pack("<IBb", dt, ch, amp) for dt, ch, amp in chunk)
            f_out.write(buf)

    written_count = len(spikes)

    size_mb = OUT_BIN.stat().st_size / 1024 / 1024
    print(f"  wrote {written_count:,} spikes ({size_mb:.2f} MB)")

    # peak burst window for summary JSON
    peak_bin = max(range(n_bins), key=lambda i: per_bin_total[i])
    peak_minute_start = t0.timestamp() + peak_bin * BIN_SECONDS
    print(f"  peak bin: {peak_bin} ({per_bin_total[peak_bin]:,} spikes)")

    # Pass 3: extract raw burst window
    burst_window_spikes = []
    with CSV_PATH.open() as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            ts_u = parse_ts(row[1]).timestamp()
            if ts_u < peak_minute_start or ts_u >= peak_minute_start + BIN_SECONDS:
                continue
            amp = float(row[2])
            ch = int(row[3])
            burst_window_spikes.append(
                [round((ts_u - peak_minute_start) * 1000), ch, round(amp, 2)]
            )
    burst_window_spikes.sort(key=lambda r: r[0])

    print(f"  burst window: {len(burst_window_spikes):,} spikes in 60s")

    out = {
        "organoid": "fs437",
        "source": "FinalSpark Neuroplatform",
        "n_electrodes": N_ELECTRODES,
        "n_spikes_total": written_count,
        "t_start_iso": t0.astimezone(timezone.utc).isoformat(),
        "t_end_iso": t_last.astimezone(timezone.utc).isoformat(),
        "t_start_unix": t0_unix,
        "span_seconds": span_seconds,
        "bin_seconds": BIN_SECONDS,
        "n_bins": n_bins,
        "per_bin_total": per_bin_total,
        "per_bin_per_ch": per_bin_per_ch,
        "per_ch_total": per_ch_total,
        "amp_hist": {
            "min_uv": -AMP_CLIP_UV,
            "max_uv": AMP_CLIP_UV,
            "nbins": amp_nbins,
            "total": amp_hist,
            "per_ch": amp_hist_per_ch,
        },
        "peak_bin": peak_bin,
        "peak_bin_t_unix": peak_minute_start,
        "burst_window": {
            "t_start_unix": peak_minute_start,
            "duration_seconds": BIN_SECONDS,
            "spikes": burst_window_spikes,
        },
    }

    OUT_JSON.write_text(json.dumps(out, separators=(",", ":")))
    size_kb = OUT_JSON.stat().st_size / 1024
    print(f"wrote {OUT_JSON} ({size_kb:,.0f} KB)")


if __name__ == "__main__":
    main()
