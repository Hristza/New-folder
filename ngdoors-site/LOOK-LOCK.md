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
