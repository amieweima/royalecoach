# Emotes

Drop Clash Royale emote PNGs here and the coach reacts with them. Missing
files are fine — the page hides any emote it can't find.

Filenames the app currently looks for:

| file | shown when |
|---|---|
| `crying-king.png` | the verdict headline (a matchup is beating you) |
| `cool-king.png` | the tilt check finds you don't tilt |
| `angry-king.png` | the tilt check finds you do tilt |

Add more moods by dropping a PNG and referencing `<Emote mood="filename" />`
in `web/app/page.tsx`.
