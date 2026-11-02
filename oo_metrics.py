"""Integrates the four OO metric modules.

analyze(source) parses pasted Python code and returns WMC, Cohesion, CBO and
RFC for every class found in it. The code is only read, never executed.
"""


from model import Model                                   # shared code analysis
from wmc import wmc                                       # Weighted Methods per Class
from cohesion import cohesion                             # Cohesion
from cbo import all_references, cbo, pair_coupling       # Coupling Between Objects
from rfc import call_graph, rfc                           # Response For a Class


def analyze(source):
    """Run all four metrics on the pasted code.

    Returns:
        {"classes": [one dict of metrics per class],
         "pairs":   [one dict per pair of classes with both coupling directions]}
    Raises SyntaxError if the pasted code isn't valid Python.
    """
    # Build the shared model once; every metric reads from it.
    model = Model(source)
    names = list(model.classes)          # class names, in the order found

    # These cover the whole program, not one class, so they're built once:
    # - refs: {class: set of other classes it references}. CBO also needs
    #   to know which classes reference a class, so it needs all of them.
    # - graph: {(class, method): [(class, method) it calls]}. RFC paths can
    #   continue into other classes' methods.
    refs = all_references(model)
    graph = call_graph(model)

    # Per-class metrics.
    classes = []
    for c in names:
        path, methods, calls = rfc(model, c, graph)
        classes.append({
            "class": c,
            "wmc": wmc(model, c),               # int
            "cohesion": cohesion(model, c),     # (var hits, total, ratio or None)
            "cbo": cbo(refs, c),                # int
            "rfc_path": path,                   # ["Doctor.admit", "Patient.__init__"]
            "rfc_methods": methods,             # methods on the path
            "rfc_calls": calls,                 # calls between them
        })

    # Coupling for each pair of classes, each pair listed once (A before B).
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ab, ba = pair_coupling(refs, a, b)          # each is 0 or 1
            pairs.append({"a": a, "b": b, "a_to_b": ab, "b_to_a": ba})

    return {"classes": classes, "pairs": pairs}
