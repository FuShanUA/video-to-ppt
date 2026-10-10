# Detection Algorithm

The helper is deliberately conservative: it prefers an extra review candidate over silently dropping a real slide.

1. **Sampling.** FFmpeg extracts low-resolution frames at 2 fps. A one-second page therefore normally produces a two-frame stable run, while a half-second page can still produce one frame.
2. **Presentation area.** Unless `--crop` is supplied, the script measures temporal pixel variance across sampled frames and finds the longest high-variance row and column ranges. It maps that region back to source pixels and adds a small top margin so titles are not cut. If the high-variance region covers nearly the whole frame, the full frame is used.
3. **Stable runs.** Consecutive frames are compared with mean absolute difference on a 64x40 grayscale feature. A run ends when the difference reaches `--change-threshold`. The default minimum run is `0.5` seconds, so single-frame pages are retained.
4. **Representative frame.** Each run uses its midpoint. This avoids transition frames at the beginning or end of a run.
5. **Duplicate removal.** Representatives are compared with mean absolute difference, a 64-bit difference hash, and a coarse RGB histogram. Only close matches are merged, so animation builds that add meaningful content remain separate.
6. **Software-demo filtering.** Each representative receives a score from border uniformity, border edge density, content edge density, and motion inside its run. Pure full-screen software demos tend to have UI edges reaching the border, low border uniformity, and continuing motion. A PPT page with an embedded screenshot tends to retain slide margins and a stable frame. Only scores at or above `--software-threshold` are excluded; uncertain pages stay.
7. **Forced timestamps.** `--force-time` inserts the nearest sampled frame and bypasses run-length, deduplication, and demo filtering. The candidate list is then sorted by frame index, and the helper rejects any non-monotonic final order. Use it for user-reported omissions.
8. **Full-frame extraction.** Accepted representatives are extracted once at full resolution with FFmpeg, cropped to the detected presentation area, and placed into a 16:9 python-pptx deck. Each slide's notes contain its source timestamp.

The output work directory also contains `manifest.tsv` and `report.json`. Use these to trace every keep, merge, or exclusion decision instead of guessing from the final PPTX alone.
