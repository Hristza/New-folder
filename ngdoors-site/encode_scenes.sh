#!/usr/bin/env bash
# Turn a raw Higgsfield clip into the two files and the poster the site ships.
#
# Ping-pong, not a hard loop. Every one of these is a one-way camera move, so the
# last frame sits well away from the first and a plain `loop` snaps back visibly.
# Playing it forward then backward makes the seam exact -- and the reversal drops
# one frame at each turn, because reverse repeats the frame it turned on and that
# repeat reads as a two-frame stutter.
#
# The bands keep their full 16:9 frame and are scaled to 1120x630 instead. Cropping
# the frame first looked like the cheaper way to fit check.py's 70 MB ceiling and
# it broke the shot: the floor and the base of the door live in the bottom fifth,
# CSS then crops the band again at desktop, and the two crops together left a wall
# with a door hanging in it and no ground. Scaling takes the same bytes off every
# row instead of taking whole rows away, so the framing stays what site.css was
# tuned for and object-position keeps doing the cropping, once.
#
# CRF 29 / VP9 40 was calibrated on the flattest wall in the set, not guessed: at
# 3x magnification crf 26 and crf 29 differ by a mean of 1.15/255 with no banding
# on the plaster, which is the failure this footage would show first.
#
# Usage: ./encode_scenes.sh <name> [<name> ...]      (reads renders/raw/<name>.mp4)
#        The hero is not scaled -- it is already small and renders as a 3:4 figure.
set -euo pipefail
cd "$(dirname "$0")"
OUT=static/scenes
mkdir -p "$OUT"

for n in "$@"; do
  src="renders/raw/$n.mp4"
  [ -f "$src" ] || { echo "missing $src"; exit 1; }

  if [ "$n" = "hero" ]; then scale=""; else scale="scale=1120:630,"; fi
  frames=$(ffprobe -v error -select_streams v:0 -count_frames \
           -show_entries stream=nb_read_frames -of csv=p=0 "$src")
  last=$((frames - 1))
  pp="[0:v]${scale}split=2[a][b];[b]reverse,trim=start_frame=1:end_frame=$last,setpts=PTS-STARTPTS[r];[a][r]concat=n=2:v=1[v]"

  ffmpeg -v error -y -i "$src" -filter_complex "$pp" -map "[v]" -an \
    -c:v libx264 -crf 29 -preset slow -pix_fmt yuv420p -profile:v high \
    -movflags +faststart "$OUT/$n.mp4"

  ffmpeg -v error -y -i "$src" -filter_complex "$pp" -map "[v]" -an \
    -c:v libvpx-vp9 -crf 40 -b:v 0 -row-mt 1 -deadline good -cpu-used 2 \
    "$OUT/$n.webm"

  # The poster is this clip's own first frame, scaled the same way, so the still and
  # the video are the same pixels. A poster cut from the old 21:9 render would sit
  # on a different part of the room and the frame would jump on first play.
  ffmpeg -v error -y -i "$src" -vf "${scale}select=eq(n\,0)" -vframes 1 \
    -c:v libwebp -quality 78 -compression_level 6 "$OUT/$n-poster.webp"

  printf "%-14s mp4 %-7s webm %-7s poster %-7s\n" "$n" \
    "$(du -h "$OUT/$n.mp4" | cut -f1)" \
    "$(du -h "$OUT/$n.webm" | cut -f1)" \
    "$(du -h "$OUT/$n-poster.webp" | cut -f1)"
done
