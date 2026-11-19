#!/usr/bin/env python3
"""The error of the world's rules, in a module of its own.

world_rules.py runs as a script (gm-rule.sh) and is imported under two names
(world_rules, lib.world_rules); a class defined there would exist once per name, and
an error raised by a block module would slip past the command's `except`. Imported
by its bare name everywhere, this module exists once.
"""


class RulesError(ValueError):
    """A rule or a change that can't be made. The message says how to fix it."""
