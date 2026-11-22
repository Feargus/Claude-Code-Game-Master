# /help - GM Command Reference

Display all available commands and tools.

---

## DISPLAY

```
================================================================
  GM ASSISTANT - Command Reference
================================================================

  CORE GAMEPLAY
  --------------------------------------------------------
  /gm              Play the game (handles everything)
  /gm end          Stop for now: the plots that moved get their sentence
  /gm cliffhanger  Stop on a cliffhanger
  /gm world        Let the world move off-screen (no ending)
  /gm choices      Action menu on/off (on | off | toggle)
  /gm character    Show character sheet & inventory
  /gm overview     View campaign state summary
  /gm status       Quick world summary

  CAMPAIGN SETUP
  --------------------------------------------------------
  /new-game           Create a new campaign world
  /import             Import a PDF/document as campaign
  /create-character   Build a new player character
  /enhance            Enrich entities with source material

  UTILITY
  --------------------------------------------------------
  /reset           Clear campaign for fresh start
  /world-check     Validate campaign consistency
  /setup           Run installation (usually auto-detected)
  /help            This help message

================================================================

  CLI TOOLS (bash tools/gm-*.sh; most print their usage when run bare)
  --------------------------------------------------------
  Session and world
  gm-session.sh     Start/end sessions, the brief (context), moves, the opening
  gm-campaign.sh    Create and switch campaigns
  gm-time.sh        In-game time
  gm-rule.sh        The world's own rules: their values, changed
  gm-scene.sh       Who is in the scene
  gm-location.sh    Add and connect locations
  gm-overview.sh    Quick world summary
  Character
  gm-player.sh      The player's sheet: fields, items, credits, XP and growth
  gm-body.sh        Wounds, armor and cyberware
  gm-condition.sh   Conditions
  Rolls and fights
  gm-skill-contest.sh  Roll a skill contest
  gm-dice.sh        Plain dice for a one-off chance (a world rule's roll: gm-rule.sh roll)
  gm-combat.sh      Enemies' wounds in a fight
  gm-mob.sh         Mobs: interchangeable enemies with stats
  People and story
  gm-npc.sh         NPC sheets: create, set fields, stats, items, places, party
  gm-faction.sh     Factions: create, show, set fields, aliases, assets, members, turns
  gm-note.sh        Facts: what happened, who knows it
  gm-consequence.sh What happens later, and what triggers it
  gm-clock.sh       Threat clocks
  gm-plot.sh        Plot threads
  gm-recall.sh      Semantic recall: setup, status (recall itself: gm-note.sh find --like)
  Source material and search
  gm-search.sh      Search world state and the source book
  gm-context.sh     Scene context with source passages
  gm-lore.sh        A grounded brief from the source book
  gm-enhance.sh     Enrich entities from the source book
  gm-extract.sh     Extract a book into a campaign

================================================================

  QUICK START
  --------------------------------------------------------
  New campaign:     /new-game
  Continue playing: /gm
  Import module:    /import

================================================================
```

---

## DETAILED HELP

If user asks for specific command help (e.g., `/help gm`), read and summarize that command file:

```bash
cat .claude/commands/[command].md | head -50
```

Provide a brief summary of what the command does and its key options.
