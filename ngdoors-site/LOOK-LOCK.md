# NG Doors — look-lock for generated imagery

Every render on this site inherits this. Written before the first generation, not after.
Read it before adding an image; do not invent a second look.

## What must stay identical across every render

| Thing | Value |
|---|---|
| Wall / ambient | `#fff5e9` warm cream, matte, no cool grey anywhere |
| Ink / shadow | `#292929`, soft, never black |
| Accent | sage `#587364` — one object per frame at most, never the wall |
| Wood | warm mid-oak, the tone of the laminate the shop actually sells |
| Light | one window, north, morning; soft falloff; no lamps, no rim light |
| Camera | eye level, ~35 mm feel, straight on or one-point; no dutch tilt |
| Grade | slightly warm, low contrast, film-flat; no teal-orange |

## The world

A real Bulgarian home, not a showroom. Panel-block apartment and small-house
proportions: narrow hallway, 2.6 m ceiling, plain plaster, a plinth, one door.
Lived-in — a coat on a hook, shoes off to one side. Empty of people.

**Never in frame:** a brand name, a logo, a price, a house number, readable text of
any kind, a face, a foreign-looking loft or a Californian window wall.

## The one rule about doors

**A render is a room, never a product.** Every scene here is atmosphere for a
category. The door in it must stay generic — plain flat leaf, no distinctive
handle, no decor pattern that could be mistaken for a catalogue model. The 623
real product photos stay real, because a customer buys the model they see and a
price sits beside it.

## Frames

| Slot | Aspect | Note |
|---|---|---|
| home hero (`.tall`) | 3:4 | hallway, door ajar, light across the floor |
| category top | 3:1 | wide band, subject in the left or right third |

## Ledger

| Date | Slot | Gens spent | File |
|---|---|---|---|
| 2026-08-28 | home hero (.tall) | 2 | static/scenes/hero-hallway-*.webp |
| 2026-08-28 | /vrati/vhodni-vrati/ | 1 | static/scenes/cat-vhodni-*.webp |
| 2026-08-28 | /vrati/interiorni-vrati/ | 1 | static/scenes/cat-interiorni-*.webp |
| 2026-08-28 | /nastilki/ | 1 | static/scenes/cat-nastilki-*.webp |
| 2026-08-28 | /granitogres/ | 2 (first was flat, had a stray basin) | static/scenes/cat-granitogres-*.webp |
| 2026-08-28 | /parvazi/ | 2 (first had no subject at all) | static/scenes/cat-parvazi-*.webp |
| 2026-08-28 | /vrati/ | 1 (rendered for /proekti/, moved here) | static/scenes/cat-proekti-*.webp |

**10 generations, ~44 credits.** /proekti/ deliberately has no scene: its own lede says the
photos come from real jobs and not from a catalogue, so a generated room would contradict the
line directly under it.

## Ledger -- the video pass (2026-08-29)

Every still above became a silent looping clip. The still stayed as the clip's own frame 0, so
the poster and the video are the same pixels and nothing jumps on first play.

| Slot | Model | Credits | Note |
|---|---|---|---|
| home hero (3:4) | seedance_2_5 | 32.5 | The only model that takes 3:4. cinematic_studio_video_v2 advertises it and the API answers 422 -- `aspect_ratio` accepts 1:1, 16:9, 9:16 only. Cropping a 9:16 down would have thrown the hero composition away, so the 6.5x price was the cheaper mistake. |
| /vrati/vhodni-vrati/ | cinematic_studio_video_v2 | 5 | |
| /vrati/interiorni-vrati/ | cinematic_studio_video_v2 | 5 | |
| /nastilki/ | cinematic_studio_video_v2 | 10 | Two takes. See below. |
| /granitogres/ | cinematic_studio_video_v2 | 5 | |
| /parvazi/ | cinematic_studio_video_v2 | 5 | |
| /vrati/ | cinematic_studio_video_v2 | 5 | |

**8 generations, 67.5 credits.** Every request needs `declined_preset_id` -- the API answers a
plain submission with a preset recommendation instead of a job, and the one it kept pushing was
"IN THE DARK", the exact opposite of a north-window morning interior.

**/nastilki/ is the lesson worth keeping.** Take one drifted 21.6/255 in mean brightness across
the clip. Take two, with an explicit exposure-lock line in the prompt, drifted 28.7 -- worse. The
frame is one near-featureless plane of oak, so the model has nothing structural to hold its
exposure against, and no wording fixes that. A third take was not bought. It was fixed in post
instead: `renders/stabilise_grade.py` pulls every frame's per-channel mean back to frame 0's.
Drift 21.6 -> 0.20, with 0.095% of samples clipped. When the same fix fails twice the approach is
wrong, not the effort.

**Framing is measured, not chosen.** A band is 3.6:1 and the clips are 16:9, so at 1440 a band
shows less than half the frame's height. A brightness profile down each poster puts the floor
line at 85% of frame height. `object-position: 50% 88%` is the lowest crop that keeps both the
floor and the door handle in shot at 390, 768 and 1440. At 50% the band came back as a bare wall
with a door hanging in it; at 72% the floor survived as six pixels.

Every clip ships as a ping-pong loop -- forward, then reversed with one frame dropped at each
turn. All of these are one-way camera moves, so a plain `loop` snaps back visibly. Measured seam
delta after the ping-pong: 1.55-2.34 out of 255, under 1%.

## Ledger -- 2026-09-29 stills (ChatGPT image model via Codex CLI)

Nine stills for the places that had no picture: five door sections without a film, the three
home-page promises, and /kontakti/. Made with `codex exec` + image generation, with
`static/scenes/hero-poster.webp` attached as the look reference and this file's rules pasted
into the prompt (prompts in `renders/gpt/batch1.txt`). Sources in `renders/gpt/*.png`,
shipped as `static/photos/<name>-640.webp` and `-1200.webp`, 519 KB for all nine.

| Slot | File | Gens |
|---|---|---|
| /vrati/aluminievi-vrati/ | aluminievi | 1 |
| /vrati/obkov-i-aksesoari/ | obkov | 1 |
| /vrati/vrati-za-servizni-pomeshteniya/ | servizni | 1 |
| /vrati/pvts-vrati-za-banya/ | banya | 1 |
| /vrati/pozharoustoychivi-vrati/ | pojaro | 1 |
| home, "Доставка" | dostavka | 1 |
| home, "Монтаж" | montazh | 1 |
| home, "Шоурум" | mostri (samples on a table, NOT her showroom) | 1 |
| /kontakti/ | kontakti | 1 |

**9 generations, no retakes.** The showroom card deliberately shows sample boards, not a room
that pretends to be her shop: a generated "showroom" beside her real address would be a false
photo of a real place. Same rule as before: a room or a still life, never a product with a price.
Stills crop into the band with `object-position: 50% 62%` (3:2 source into a 3.6:1 band).

## Product photo update — 2026-10-03

The owner explicitly requested ChatGPT renders of the product catalogue. This overrides
the earlier rule that generated images may show only generic rooms. Each render uses the
original product image as a reference and must preserve its model, finish, panel design,
frame and hardware. Generated project photos must not replace the real installation gallery.

The accepted and pending source photos are recorded in `renders/manifest.json`. Original
references remain in `renders/originals/` and Git history. Generated masters are kept in
`Outputs/ngdoors-product-renders/`; the website receives the existing 600/1200 WebP sizes.
`apply_render.py` records an image only after it has been visually inspected.
