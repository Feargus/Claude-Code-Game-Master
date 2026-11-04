# /enhance - Entity Enhancement from Source Material

Enhance entities or search for source material using RAG.

## Arguments

$ARGUMENTS - Entity name OR search keywords (e.g., "Grimjaw", "Vey Vault security", "who runs the Spine")

## Philosophy

**GM judges relevance, not the code.** The RAG system returns semantically similar passages without strict filtering. You (the GM) decide what's useful. This prevents filtering out valuable content due to naming mismatches (e.g., "Floor 2" vs "second floor").

## Workflow

### Step 1: Determine Entity Type

First, find what kind of entity we're enhancing:

```bash
bash tools/gm-enhance.sh find "$ARGUMENTS"
```

This returns one of:
- `npc` - Character enhancement
- `location` - Place enhancement
- `site` - The target of a run, a job or a dungeon, laid out as areas
- `item` - A notable object
- `plot` - Quest or story hook

If no entity found, use **Option A: Exploratory Search** instead.

---

### Option A: Exploratory Search (No Specific Entity)

Use when searching for general information:

```bash
bash tools/gm-enhance.sh search "$ARGUMENTS" -n 15
```

Examples:
- `search "vault lower levels"` - Find content about a site
- `search "Grimjaw background personality"` - Learn about an NPC
- `search "who guards the server core"` - Find who stands in the way

**Process the results:**
1. Read through returned passages
2. Extract relevant details for the current scene/entity
3. Weave information naturally into gameplay or entity updates

---

### Option B: NPC Enhancement

When entity type is `npc`:

#### Step 1: Query Source Passages

```bash
bash tools/gm-enhance.sh query "$ARGUMENTS" --type npc
```

#### Step 2: Propose Enhancements

Present to the GM:

```
**NPC Found:** [Name]

**Current State:**
- Description: [current description or "None"]
- Context passages: [count]

**From Source Material:**
Based on [X] passages, I can add:
- [Personality trait from source]
- [Background detail from source]
- [Relationship or motivation]
- [N context passages for future reference]

**Apply these enhancements?**
```

#### Step 3: Apply If Approved

```bash
bash tools/gm-enhance.sh apply "$ARGUMENTS" --context "passage 1" --context "passage 2"
```

For description updates:
```bash
--description "Enhanced description text"
```

---

### Option C: Site Enhancement

When entity type is `site` (or a location the player is about to make a run on):

1. **Check whether it is laid out:**
   ```bash
   bash tools/gm-enhance.sh site-check "$ARGUMENTS"
   ```
   It lists the site's areas (locations saved as `<Site> - <Area>`).
2. **Query the source:**
   ```bash
   bash tools/gm-enhance.sh query "$ARGUMENTS" --type site -n 15
   ```
3. **No areas yet:** spawn `site-architect` with the passages (names, security, who holds it, what's kept there). It saves the areas and connections itself. Use the source's names exactly; improvise only the gaps.
4. **Areas exist:** offer to add the passages as context to the site, or to update area descriptions with source details (`gm-location.sh describe`).

Lay a site out when the player commits to the job, not at the door. See `gm-sites`.

---

## Command Reference

| Command | Use For |
|---------|---------|
| `search "keywords"` | Exploratory queries, concepts, general info |
| `find "name"` | Locate a specific entity and determine type |
| `query "name"` | Get passages for a known entity |
| `apply "name"` | Save enhancements to entity |
| `summary "name"` | Full entity + passages report |
| `list-unenhanced` | Find entities needing enhancement |
| `site-check "name"` | List a site's areas |

## Notes

- Requires a populated vector store (run `/import` first)
- Uses additive merging - existing context is preserved
- Context passages capped at 20 per entity
- Works for NPCs, locations, items, plots, sites
- **No strict name filtering** - GM judges all passage relevance
- **RAG Priority**: Use source material for accuracy over improvisation
- **Sites**: lay out a run's target with `site-architect` when the player commits to the job
