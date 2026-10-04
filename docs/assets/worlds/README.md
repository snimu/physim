# Landing-page film

`ds3_014-intro.mp4` is a presentation excerpt of the historical `ds3_014`
simulation, with the fields combined in one view. It is not a new simulation or
an evaluation rollout. The original research animations, including plots, remain
in `../blobs/p7_world_ds3_014.gif` and `../blobs/p7_world_ds3_014_long.gif`.

The user supplied the source recording on 2026-09-15:
`Screen Recording 2026-08-24 at 11.06.59 AM (1).mov`, SHA-256
`3a25fc29801eea1907df4d83c9b5157448dbe08d1dc72c73715a706a8fe91281`.
The recording is retained locally. The web export removes the title, timestamp,
and border, preserves playback order and speed, and has no audio. Its restart
is an ordinary replay, not a claim of periodic dynamics.

Export with FFmpeg using `crop=418:418:18:29,fps=30`, H.264, `yuv420p`, CRF 19,
the slow preset, `+faststart`, and no metadata. `ds3_014-intro.jpg` is the frame
at five seconds, used as the video's loading poster. These are static media
inputs preserved by `scripts/build_docs.py`.

## Earlier media

The rest of this folder comes from earlier versions of the page and is not shown on
the current one; the BF and p4g2_044 films it uses are in `../bf-thread/`.
`bf-fields`, `xv-fields` and `p4g2_044-fields` (MP4, poster and provenance JSON)
are field films from `scripts/render_world_movies.py`. `early-travel` and
`early-binding` come from `scripts/render_intro_examples.py`. `scripts/check_docs.py`
verifies all five against their records; `docs_source/README.md` describes both
generators.

## BF and XV field snapshots

`bf-sham.png` and `bf-trail-pulse.png` show activator 0 at time 50 from
recorded no-source and five-unit trail-pulse experiments. The source pulse has
amplitude 0.05 on public port 2 and runs from t=0 to t=5. The two displayed
realizations use independent noise (recorded truth seeds 51000 and 51005) and
identical initial fields. Dashed contours mark the initial activator level 0.5;
the pink cross marks the fixed source in both panels.

`xv-0.png`, `xv-125.png`, and `xv-250.png` show the first recorded unforced,
coupled XV continuation at those times (recorded truth seed 53001). The white
contour marks partner activator 1 at level 0.5. All three use the same spatial
window; they do not recenter on the moving structures.

All panels render the original grid values with nearest-neighbor display and
the common activator color scale in `activator-scale.png` (−1 to 1.6). Scale
bars measure five spatial units. These are spatial crops, not full-domain plots.
Exact crop arrays and source hashes live in `docs_source/data/world-visuals.npz`
and its JSON sidecar. Regenerate with `scripts/render_world_visuals.py`;
no simulation or inference is run. The original scientific report and its
figures are unchanged.
