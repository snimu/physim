"""Encode exact Agg canvas bytes, checking the frame dimensions on every write."""

import subprocess
from contextlib import contextmanager

import numpy as np
from PIL import Image


@contextmanager
def video_writer(fig, path, fps=16):
    fig.canvas.draw()
    height, width, channels = np.asarray(fig.canvas.buffer_rgba()).shape
    assert channels == 4
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgba",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-crf",
        "19",
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-threads",
        "1",
        str(path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)

    references = []
    count = 0

    def frame(poster=None):
        nonlocal count
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        if rgba.shape != (height, width, 4):
            raise ValueError(f"Canvas dimensions changed: {rgba.shape}")
        if count == 0:
            references.append(rgba[:, :, :3].copy())
        if len(references) == 1:
            references.append(rgba[:, :, :3].copy())
        else:
            references[1] = rgba[:, :, :3].copy()
        count += 1
        process.stdin.write(rgba.tobytes())
        if poster:
            Image.fromarray(rgba).convert("RGB").save(poster, quality=95)

    try:
        yield frame
    finally:
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError(f"Video encoding failed: {path}")

    # Decode the actual encoded first/last frames. This catches rawvideo stride
    # mismatches that can leave source/poster images correct but shear the MP4.
    selected = [0] if count == 1 else [0, count - 1]
    filt = "+".join(f"eq(n,{i})" for i in selected).replace(",", r"\,")
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            f"select={filt}",
            "-vsync",
            "0",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    encoded_height, encoded_width = height + height % 2, width + width % 2
    images = np.frombuffer(decoded, dtype=np.uint8).reshape(len(selected), encoded_height, encoded_width, 3)
    errors = [float(np.abs(im[:height, :width].astype(float) - ref).mean()) for im, ref in zip(images, references)]
    if max(errors) > 5:
        raise ValueError(f"Encoded frames do not match source canvas: {errors}")
    frame.validation = dict(
        width=encoded_width,
        height=encoded_height,
        frames=count,
        checked_frames=selected,
        mean_absolute_pixel_errors=errors,
    )
