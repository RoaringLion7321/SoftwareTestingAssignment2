"""Cohesion of a class.

Cohesion = member variable interactions / total number of interactions.

An interaction is one distinct thing a method uses: one of its own class's
member variables, one of its own class's methods, or a member (variable,
method or constructor) of another user-defined class. Each distinct thing is
counted once per method. Built-ins such as ``str.strip`` or ``list.append``
are not counted. A class with no interactions has no cohesion value (None).
"""


def cohesion(model, cname):
    """Returns (member_var_interactions, total_interactions, ratio or None)."""
    var_hits = total = 0
    for m in model.classes[cname].methods:
        for kind, owner, _ in model.interactions(cname, m):
            total += 1
            if kind == "var" and owner == cname:
                var_hits += 1
    return var_hits, total, (var_hits / total if total else None)
