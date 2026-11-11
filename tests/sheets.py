"""Small sheets (lib/sheet.py's format) for test fixtures."""


def player(name, **sections):
    """A minimal player sheet; sections given are added as they are."""
    sheet = {"identity": {"name": name}, "stats": {"attributes": {}}, "body": {"zones": {}}}
    sheet.update(sections)
    return sheet


def npc(name, aliases=None, places=None, **sections):
    """A minimal NPC sheet, optionally with aliases and usual places."""
    sheet = {"identity": {"name": name}}
    if aliases:
        sheet["identity"]["aliases"] = list(aliases)
    if places is not None:
        sheet["places"] = {"usual": list(places)}
    sheet.update(sections)
    return sheet
