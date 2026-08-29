"""Pull a clip's exposure back to its own first frame, frame by frame.

Only needed for the laminate-floor shot. That frame is one near-featureless plane,
so the model has no structure to hold its exposure against and the grade climbs:
measured 21.6/255 across five seconds on take one and 28.7 on take two, which is
why a third take was not bought -- the prompt is not the lever, the shot is.

Ping-ponged, a monotonic climb becomes a slow brightness swell every ten seconds.
On a cream-walled site that pulse reads as a broken video, so it is corrected here
instead: each frame is scaled per channel so its mean matches frame zero. The scale
is a few percent, and the clip is checked for clipped highlights afterwards, because
a gain that crushes the light on the wall would trade one visible defect for another.
"""
import subprocess
import sys

import numpy as np

src, dst = sys.argv[1], sys.argv[2]
w, h = (int(x) for x in subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=width,height", "-of", "csv=p=0", src],
    capture_output=True, text=True).stdout.strip().split(","))

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src,
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                     capture_output=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32)
base = frames[0].reshape(-1, 3).mean(0)

out = np.empty_like(frames)
gains, clipped = [], 0
for i, f in enumerate(frames):
    g = base / np.maximum(f.reshape(-1, 3).mean(0), 1e-6)
    gains.append(g)
    c = f * g
    clipped += int((c > 255).sum())
    out[i] = np.clip(c, 0, 255)

g = np.array(gains)
print("frames %d  gain range %.4f..%.4f  clipped %.4f%% of samples"
      % (len(frames), g.min(), g.max(), 100.0 * clipped / out.size))

after = [abs(out[i].reshape(-1, 3).mean(0) - base).max() for i in range(len(out))]
print("drift after correction: max %.2f (was measured at 21.6 before)" % max(after))

subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", "%dx%d" % (w, h), "-r", "24", "-i", "-",
                "-c:v", "libx264", "-crf", "16", "-preset", "slow",
                "-pix_fmt", "yuv420p", dst],
               input=out.astype(np.uint8).tobytes(), check=True)
print("wrote", dst)
