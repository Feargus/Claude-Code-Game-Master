# Output: what the commands print

*Claude, 2026-11-22. A target, not a description: new output follows it, and older output
moves over when its module is touched for another reason, as the error style did. No
conversion pass. "Where we are" at the end lists what is still to move.*

## Who reads it

The GM: a language model reading the output in its context, often only the first line
(`| head -1`), often with the rest of the output dropped. So output is short, readable
text that says what happened and what to do next. There is no machine format: the tests
call the Python functions, not the commands, and no script parses a command's output
(`--json` is being removed, todo).

## Streams and exit codes

- **Standard output:** everything but errors.
- **Standard error:** `[ERROR]` lines, and only those.
- **Exit code:** 0 when the command did what it was asked, 1 when it didn't.

## Square brackets: for the GM

Text in square brackets is for the GM and is never narrated as it stands. At the start
of a line it is a **marker** (what to do with the line); before a fact's text it is a
**mark** (what the character knows of it). Nothing else uses square brackets.

## Markers

A marker is the first word of a line the GM scans, and says what the GM does with it.
Lines that only add detail to the line above are indented two spaces and carry none.

| Marker | Meaning | The GM … |
|---|---|---|
| `[SUCCESS]` | The command did what it was asked. The first line, naming what it made or changed, with its id: `[SUCCESS] Recorded fact f83` | nothing |
| `[ERROR]` | It didn't (below). On standard error | fixes it |
| `[CHECK]` | Something to judge now, with the command if the answer is yes: `[CHECK] f43 may trigger c12: "Pell bids …"`, `[CHECK] Tied but no Relation set: …` | judges it |
| `[DO]` | Something to play now, no judgment needed: faction turns owed, a growth due, a rule result's "Do now" | acts |
| `[FIRED]` | Something happened by itself: a consequence fired, a clock filled | plays it out |
| `[STOPPED]` | Time stopped partway through a step: what happened then, and the command to go on | decides: play it or go on |
| `[NOTE]` | Worth knowing, nothing to do: `[NOTE] f52 put in The Sold Contract by recall; if wrong: …` | knows it |

A new marker is added here first, with its meaning, and only when none of these fits.

## Lines

- **The first line alone says whether it worked, and the id** of what was made or changed.
- **Everything after it is something the GM doesn't already know.** Never read back what
  the GM just typed (the fact's own text, every field that was set).
- **An action ends with the full command**, ready to run: `bash tools/gm-note.sh plot f52 --add "The Sold Contract"`.
- **Nothing to report: no line.** Not `(nothing triggered)`, not `No facts match.` after a
  command whose job was something else. A lookup that finds nothing says so in one line.
- **One thing per line.** A list of several is several lines, not one line with semicolons.
- **Numbers the player must not see** are never in text meant for narration (the GM's
  instructions keep them out of the story); output for the GM may show them.

## Ids

A record with a short name that never changes is called by its name; a record without
one gets a letter and a number, in the order made.

| Record | Id | Written as |
|---|---|---|
| fact | `f` and a number | `f43` |
| consequence | `c` and a number (target; today upstream's 8 hex characters, shown as the first 4: `[2563]`) | `c12` |
| NPC | the name | `npc:Matron Ysabet Corvane` in ids, the name in text |
| location | the name | `location:The Saffron House` in ids, the name in text |
| faction | a short id | `faction:houses` in ids, the name in text |
| plot, clock, world rule, glossary term | the name (one to four words; never changes) | `The Sold Contract`, `Sealing`, `Hunger` |
| the character | `player` in ids | the character's name in text |

## What the character knows: the marks inside a line

Put before the text they mark, in square brackets, upper case.

| Target mark | Meaning | Today |
|---|---|---|
| `[SECRET]` | Nobody knows it but the GM (a fact with no holders) | `[SECRET]`, worked out from the holders each time |
| `[HIDDEN]` | The character doesn't know it; others may (no `player` or `public` among the holders) | `[HIDDEN FROM PLAYER]`, worked out from the holders each time |
| `[SIGNS ONLY]` | A world rule's value the character sees only by its effects | `[HIDDEN: show only its signs]`, stored per rule and holder |
| `[MEMBERS ONLY]` | A faction membership only its members know | `(SECRET: only its members know; nobody else acts on it)`, stored at `join --secret` |
| `[WRONG → f12]`, `[PARTIAL → f12]` | A wrong or partial version, and the fact that holds the truth | `[WRONG; the truth is f12]`, `[PARTIAL; fuller: f12]`, stored |

`SECRET` and `HIDDEN` mean one thing each: today both words also name a second thing (a
membership, a rule's value). The character is part of the public but not of the street
(decided 2026-11-22, for now: the street is not properly built yet), so a fact the street
knows is still hidden from the character.

## Errors

- A function that can't do its job raises an error whose message says what is wrong and
  how to fix it (the module's own error class, or `ValueError`). It never prints
  `[ERROR]` and returns `False`, `{}` or `""`.
- The command line catches it, prints `[ERROR] <message>` on standard error (not
  `Error:`, not standard output) and exits with 1.
- A file that can't be read or written raises `JsonFileError` (`lib/json_ops.py`), which
  stops any command with one plain message.
- A refusal says that nothing was changed, when that isn't obvious: "Nothing was recorded."

## Words

One word, one meaning, the same in the output, `CLAUDE.md`, the skills and the command
files. A new idea gets its word here before it is used.

| Word | Means | Not |
|---|---|---|
| **fact** | One sentence or two that happened or is true (`gm-note.sh`) | note, event, entry |
| **holders** | Who knows a fact | witnesses, known by |
| **about** | Who or what a fact concerns | tags |
| **version** | A wrong or partial fact pointing to the true one | lie, rumour (those are what a version is in the story) |
| **consequence** | What happens when one of its triggers matches; it **fires** once, is **resolved** once played out, and can be **rearmed** | event, reaction |
| **trigger** | What a consequence waits for; a recorded fact **triggers** an `on_fact` one | condition, event |
| **clock** | Segments that fill; **full**, or **due** at a time | timer, countdown |
| **plot** | What the story turns on; it **stands** somewhere, has an **owner**, **involves** NPCs, locations and factions | thread, quest, arc |
| **scene** | Who is **present** where the character is; NPCs **enter** and **leave** | |
| **NPC** | Anyone in the world but the character (`gm-npc.sh`, `npc:<name>`) | person |
| **location** | A place in the world (`gm-location.sh`, `location:<name>`) | place, spot |
| **link**, **suggest** | Recall *links* a fact to a plot or NPC by itself, or *suggests* it | tag, offer |
| **world rule** | A rule of the campaign's own (`gm-rule.sh`); **Standing**, **Relation**, the **powers** are the repo's | signature system, mechanic |
| **the character** | The player's character, in text | the player, the PC |
| **currency** | What amounts are shown in (the world bible's word) | credits (only the data's name) |

## Where we are (2026-11-22)

- Markers still in the code that this retires: `[WARNING]` and `[INFO]` (become `[CHECK]`
  or `[NOTE]`), `[REACTIVITY]` and `[WORLD TICK]` (become `[FIRED]`, or nothing when
  nothing happened), `TIME STOPPED` (`[STOPPED]`), `FACTION TURNS OWED` and `Do now:`
  (`[DO]`), upstream's capitals `ITEM_ADDED`, `ITEM_MOVED`, `ITEM_REMOVED`, `CREDITS_GAINED`,
  `CREDITS_SPENT`, `LOOT`, `DEATH`, `GROWTH_DUE`, `XP_GAIN`, `GROWN`, `RAISED`, `PERK`
  (become `[SUCCESS]` sentences).
- The fact's output reads its own text back (`[SUCCESS] Recorded fact f83: <the text>`).
- Semantic recall's lines after a fact carry no marker yet (they become `[CHECK]` for a
  consequence it may trigger, `[NOTE]` for a link it made, `[CHECK]` for a suggestion).
- Consequence ids are upstream's hex codes; the hiding marks are today's.
- `Error:` instead of `[ERROR]`, and `[ERROR]` on standard output: `todo.md` → Review.
