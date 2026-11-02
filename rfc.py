"""Response For a Class (RFC).

RFC is the longest method-to-method call path that starts at one of the
class's methods. The path can continue into methods of other user-defined
classes, and never visits the same method twice (so recursion and call
cycles end). It is reported as the number of methods on the path and the
number of calls between them, for example:

    Doctor.schedule_appointment -> Patient.add_appointment
    methods = 2, calls = 1
"""


def call_graph(model):
    """(Class, method) -> list of (Class, method) it calls (constructors call __init__)."""
    graph = {}
    for c in model.classes.values():
        for m in c.methods:
            targets = set()
            for kind, owner, name in model.interactions(c.name, m):
                if kind == "method":
                    targets.add((owner, name))
                elif kind == "ctor":
                    r = model.lookup(owner, "__init__")
                    if r and r[0] == "method":
                        targets.add((r[1], "__init__"))
            graph[(c.name, m)] = sorted(targets)
    return graph


def _longest_path(graph, node, visited):
    best = [node]
    for nxt in graph.get(node, []):
        if nxt not in visited:
            path = [node] + _longest_path(graph, nxt, visited | {nxt})
            if len(path) > len(best):
                best = path
    return best


def rfc(model, cname, graph):
    """Returns (path as list of 'Class.method', methods, calls)."""
    best = []
    for m in model.classes[cname].methods:
        path = _longest_path(graph, (cname, m), {(cname, m)})
        if len(path) > len(best):
            best = path
    names = [f"{c}.{m}" for c, m in best]
    return names, len(names), max(len(names) - 1, 0)
