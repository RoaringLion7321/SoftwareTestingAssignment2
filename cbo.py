"""Coupling Between Objects (CBO).

Class A references class B when a method of A calls a method of B, accesses
a variable of B, or constructs a B. CBO(A) is the size of the set of classes
that A references together with the classes that reference A; each class is
counted once even when the reference goes both ways.

For a pair of classes, each direction is reported separately:
CBO(A->B) is 1 if A references B and 0 otherwise, and likewise CBO(B->A).
"""


def references(model, cname):
    """Other user-defined classes that this class references."""
    return {owner for m in model.classes[cname].methods
            for _, owner, _ in model.interactions(cname, m) if owner != cname}


def all_references(model):
    return {c: references(model, c) for c in model.classes}


def cbo(refs, cname):
    coupled = set(refs[cname]) | {other for other, r in refs.items() if cname in r}
    coupled.discard(cname)
    return len(coupled)


def pair_coupling(refs, a, b):
    """(CBO(A->B), CBO(B->A))."""
    return int(b in refs[a]), int(a in refs[b])
