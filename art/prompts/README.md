# Image prompts

Each file is one image, named after its id in `data/world.json`. The style
blocks and workflow are in `../STYLE.md`. To see what's made and what's left:

```
npm run art:status
```

- `scenes/`: the title.
- `rooms/`: one per room (31, plus the 3 already made). The 6 "lost" clue
  rooms share two pictures in `moments/` instead.
- `items/`: the 20 objects (transparent backgrounds).
- `moments/`: deaths, the two lost scenes, and victory.

## Suggested order

Paint outwards from the start, so the game fills in the way a player
explores it:

1. **Around the bank**: mountain-path, evergreen-glade, deep-river,
   old-stone-wall.
2. **Over the wall**: old-wall, rusty-gate, yellow-flowers, mossy-steps,
   tower, and forest-crossroads, charcoal-hut, forest-witches, forest-edge.
3. **Caves**: cave-entrance, dark-tunnels, beautiful-chamber.
4. **The mountain**: mountain, maze, trolls, oak-door, treasure-room, giant,
   damp-tunnels.
5. **Across the river to the castle**: river-south-bank, moat, courtyard,
   coach-house, grand-hall, wizards-kitchen, dungeon, small-room.

Make objects whenever you like, perhaps one or two alongside each batch of
rooms. Make moments last, attaching the room each one happens in.

When a later room is similar to one you've already made (another forest,
another tunnel), attach that one too. Some prompts suggest which.
