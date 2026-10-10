---
name: video-to-ppt
description: Extract presentation slides from a video, remove pure software-demo footage, and build a 16:9 PPTX while preserving slides that contain software screenshots.
metadata:
  short-description: Turn videos into clean slide decks
---

# Video to PPT

Use this skill when the user provides a recorded talk, webinar, or screen-shared presentation and wants its slides reconstructed as a PPTX. It also applies when the user asks to avoid missing short-lived slides or to exclude live software demos.

## Workflow

Run the deterministic helper first:

```bash
~/.codex/skills/video-to-ppt/scripts/video_to_ppt.py INPUT.mp4
```

The helper samples at 2 fps by default, detects the presentation area, finds stable runs, removes duplicate pages, excludes only high-confidence pure software demos, extracts full-resolution representative frames, and writes a 16:9 PPTX. It keeps slides whose layout still has presentation margins around an embedded software screenshot.

After the first run, inspect:

- `WORKDIR/review/contact_sheet.jpg` for page order and missing pages.
- `WORKDIR/manifest.tsv` for timestamps, run lengths, software scores, and exclusion reasons.
- `WORKDIR/report.json` for the detected crop and final counts.

If a page is missing, rerun with one or more explicit timestamps. These pages bypass run-length, deduplication, and software-demo filtering:

```bash
~/.codex/skills/video-to-ppt/scripts/video_to_ppt.py INPUT.mp4 \
  --force-time 01:13:49 --force-time 01:14:49
```

Forced timestamps are inserted in chronological order, never appended to the end. The helper validates that final page indexes are strictly increasing before extracting full frames.

If the presentation area is wrong, rerun with a source-pixel crop:

```bash
~/.codex/skills/video-to-ppt/scripts/video_to_ppt.py INPUT.mp4 --crop 304,80,976,610
```

If a pure software demo remains, lower `--software-threshold` from the default `5` only after checking that pages containing screenshots have clear slide margins. If a PPT page containing a screenshot is removed, raise the threshold or use `--force-time`. Do not classify a page as a demo merely because it contains an application image.

For unusually quick transitions, raise sampling density with `--fps 3` or `--fps 4`. For noisy sources, inspect `manifest.tsv` before changing thresholds; a global threshold change can remove real pages.

Read [references/algorithm.md](references/algorithm.md) when changing detection behavior, debugging a missed page, or explaining why a page was kept or excluded.
