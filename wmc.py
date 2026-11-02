"""Weighted Methods per Class (WMC).

WMC is the sum of the cyclomatic complexity of each method written in the
class. Cyclomatic complexity starts at 1 and adds 1 for every decision point:
if / elif, for / async for / while, each match case except the default
``case _``, except, each and / or operator, and the ternary ``x if c else y``.
Comprehension ``for`` and ``if`` clauses count too.
"""
import ast


def cyclomatic_complexity(fn):
    """1 + number of decision points in the method."""
    cc = 1
    for n in ast.walk(fn):
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)):
            cc += 1
        elif isinstance(n, ast.BoolOp):
            cc += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            cc += 1 + len(n.ifs)
        elif hasattr(ast, "match_case") and isinstance(n, ast.match_case):
            default = (isinstance(n.pattern, ast.MatchAs) and n.pattern.pattern is None
                       and n.pattern.name is None)
            if not default:
                cc += 1
    return cc


def wmc(model, cname):
    return sum(cyclomatic_complexity(fn) for fn in model.classes[cname].methods.values())
