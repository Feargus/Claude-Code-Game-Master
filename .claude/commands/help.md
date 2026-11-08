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
  /gm save         End the session and check everything was saved
  /gm end          End the session, recording only what is
  /gm cliffhanger  End the session on a cliffhanger
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
  gm-scene.sh       Who is in the scene
  gm-location.sh    Add and connect locations
  gm-overview.sh    Quick world summary
  Character
  gm-player.sh      XP, credits, inventory, counters, level-ups
  gm-body.sh        Wounds, armor and cyberware
  gm-condition.sh   Conditions
  Rolls and fights
  gm-skill-contest.sh  Roll a skill contest
  gm-combat.sh      Enemies' wounds in a fight
  People and story
  gm-npc.sh         Create and update NPCs
  gm-note.sh        Facts: what happened, who knows it
  gm-consequence.sh What happens later, and what triggers it
  gm-clock.sh       Threat clocks
  gm-plot.sh        Plot threads
  gm-recall.sh      Long-term memory
  Source material and search
  gm-search.sh      Search world state and the source book
  gm-context.sh     Scene context with source passages
  gm-lore.sh        A grounded brief from the source book
  gm-enhance.sh     Enrich entities from the source book
  gm-extract.sh     Extract a book into a campaign
  gm-image.sh       Scene images (needs OPENAI_API_KEY)

================================================================

  QUICK START
  --------------------------------------------------------
  New campaign:     /new-game
  Continue playing: /gm
  Import module:    /import

  SCENE IMAGES (optional)
  --------------------------------------------------------
  The GM illustrates often, framed as an in-world chronicler's art:
    bash tools/gm-image.sh chronicler --name "Astreus" \
      --style "rough Frazetta-esque ink wash, woodcut" \
      --persona "a drunk court-scholar who exaggerates the gore"
    bash tools/gm-image.sh generate --title "..." --prompt "..."
  The locked --style is auto-added to every prompt so the gallery
  reads like one artbook. Saves a PNG + prints a clickable file://
  link. Needs OPENAI_API_KEY in .env; gm-image.sh log shows spend.

================================================================
```

---

## DETAILED HELP

If user asks for specific command help (e.g., `/help gm`), read and summarize that command file:

```bash
cat .claude/commands/[command].md | head -50
```

Provide a brief summary of what the command does and its key options.
