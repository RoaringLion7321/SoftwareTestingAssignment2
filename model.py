"""Shared model for the OO metrics: parses pasted code, finds classes,
their members, simple types, and what each method interacts with.

The code is never executed. Python's ``ast`` module turns the text into a
syntax tree, and everything here is worked out by walking that tree.

Types are stored as small tuples:
    ("obj", "Patient")   an instance of Patient
    ("cls", "Patient")   the class object itself (Patient.x, or cls in a classmethod)
    ("list", "Patient")  a collection whose items are Patient objects
    None                 unknown / not a user-defined class
"""
import ast


# ---------------------------------------------------------------------------
# Shared model: classes, their members, and simple type inference
# ---------------------------------------------------------------------------

class _Class:
    """Everything the tool stores about one class from the pasted code."""

    def __init__(self, node):
        self.name = node.name            # e.g. "Doctor"
        self.node = node                 # the ast.ClassDef node
        # Parent classes, only when written as a plain name: class Doctor(Person)
        self.bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        # Methods written directly in the class body (nested functions are not methods)
        self.methods = {n.name: n for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.vars = set()        # member variable names
        self.attr_types = {}     # member variable -> ('obj' | 'list', ClassName)


def _self_name(fn):
    """Name of the first parameter (self / cls), or None for staticmethods."""
    # A staticmethod has no self, so its first parameter is an ordinary argument.
    if any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in fn.decorator_list):
        return None
    args = fn.args.posonlyargs + fn.args.args
    return args[0].arg if args else None


def _is_classmethod(fn):
    """True if the method has @classmethod (its first parameter is the class)."""
    return any(isinstance(d, ast.Name) and d.id == "classmethod" for d in fn.decorator_list)


class Model:
    """Parsed program: classes, member variables, types and interactions."""

    def __init__(self, source):
        # 1. Parse the text. A SyntaxError here is caught and shown by the GUI.
        tree = ast.parse(source)
        # 2. Find every class definition (including nested ones), keyed by name.
        self.classes = {n.name: _Class(n) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        # 3. Find the member variables of each class.
        self._collect_vars()
        # 4. Work out member variable types. Types can depend on other classes'
        #    types, so a few passes let the information spread between them.
        for _ in range(3):              # repeat so types can flow between classes
            self._collect_attr_types()
        # 5. Work out local variable types for every method, once, so the
        #    metric modules can reuse them.
        self.envs = {(c.name, m): self.method_env(c.name, fn)
                     for c in self.classes.values() for m, fn in c.methods.items()}

    # --- members -----------------------------------------------------------
    def _collect_vars(self):
        """Fill each class's `vars` with its member variable names."""
        for c in self.classes.values():
            # Class-level variables: `count = 0` or `name: str` in the class body.
            for n in c.node.body:       # class-level variables
                if isinstance(n, ast.Assign):
                    c.vars.update(t.id for t in n.targets if isinstance(t, ast.Name))
                elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                    c.vars.add(n.target.id)
            # Instance variables: anything assigned through self in any method,
            # e.g. `self.name = ...` or `self.total += 1` (attribute in Store context).
            for fn in c.methods.values():   # self.x = ... inside methods
                me = _self_name(fn)
                for n in ast.walk(fn):
                    if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                            and isinstance(n.value, ast.Name) and n.value.id == me):
                        c.vars.add(n.attr)

    def _collect_attr_types(self):
        """Fill each class's `attr_types` with the types of its member variables."""
        for c in self.classes.values():
            # Annotated class-body fields, e.g. `owner: Doctor` (dataclass style).
            for n in c.node.body:
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                    t = self.ann_type(n.annotation)
                    if t:
                        c.attr_types[n.target.id] = t
            for fn in c.methods.values():
                me, env = _self_name(fn), self.method_env(c.name, fn)

                def is_self_attr(t):
                    """True for an expression of the form `self.something`."""
                    return (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                            and t.value.id == me)

                for n in ast.walk(fn):
                    # self.doctor = Doctor(...)   or   self.doctor = doctor (typed param)
                    if isinstance(n, ast.Assign):
                        t = self.type_of(n.value, env)
                        for tg in n.targets:
                            if t and is_self_attr(tg):
                                c.attr_types[tg.attr] = t
                    # self.patients: list[Patient] = []
                    elif isinstance(n, ast.AnnAssign) and is_self_attr(n.target):
                        t = self.ann_type(n.annotation) or (n.value and self.type_of(n.value, env))
                        if t:
                            c.attr_types[n.target.attr] = t
                    # self.patients.append(p) where p is a Patient
                    #   -> self.patients is a collection of Patient
                    elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                          and n.func.attr in ("append", "add", "insert")
                          and is_self_attr(n.func.value) and n.args):
                        t = self.type_of(n.args[-1], env)      # self.items.append(Item(...))
                        if t and t[0] == "obj":
                            c.attr_types[n.func.value.attr] = ("list", t[1])

    def lookup(self, cname, name, seen=()):
        """Find which class (cname or a user-defined base) defines `name`.

        Returns ("method", owner), ("var", owner) or None. `owner` is the class
        that actually defines the member, which may be a parent class.
        """
        c = self.classes.get(cname)
        # Unknown class, or we've already been here (circular inheritance).
        if not c or cname in seen:
            return None
        if name in c.methods:
            return ("method", cname)
        if name in c.vars:
            return ("var", cname)
        # Not defined here: search the parent classes.
        for b in c.bases:
            r = self.lookup(b, name, seen + (cname,))
            if r:
                return r
        return None

    def attr_type(self, cname, name, seen=()):
        """Type of member `name` of class `cname` (searching parent classes too).

        For a method, this is the type from its return annotation.
        """
        c = self.classes.get(cname)
        if not c or cname in seen:
            return None
        if name in c.attr_types:
            return c.attr_types[name]
        if name in c.methods:
            return self.ann_type(c.methods[name].returns)   # def f(self) -> Patient
        for b in c.bases:
            t = self.attr_type(b, name, seen + (cname,))
            if t:
                return t
        return None

    # --- types -------------------------------------------------------------
    def ann_type(self, a):
        """Turn an annotation like Patient, list[Patient], Optional[Patient] into a type."""
        if a is None:
            return None
        # Forward reference written as a string: "Patient"
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            try:
                a = ast.parse(a.value, mode="eval").body
            except SyntaxError:
                return None
        # Plain class name. Only user-defined classes count; int, str, ... give None.
        if isinstance(a, ast.Name) and a.id in self.classes:
            return ("obj", a.id)
        if isinstance(a, ast.BinOp):                     # Patient | None
            return self.ann_type(a.left) or self.ann_type(a.right)
        # Generic types: list[Patient], set[Patient], Optional[Patient], ...
        if isinstance(a, ast.Subscript):
            inner = a.slice
            if isinstance(inner, ast.Tuple):
                inner = inner.elts[-1]                   # dict[str, Patient]
            t = self.ann_type(inner)
            # Name of the generic itself: `Optional` or `typing.Optional`
            base = a.value.id if isinstance(a.value, ast.Name) else getattr(a.value, "attr", "")
            if t and base == "Optional":
                return t                                 # Optional[X] is just an X
            if t:
                return ("list", t[1])                    # any other container of X
        return None

    def type_of(self, e, env):
        """Best-effort static type of an expression: ('obj'|'cls'|'list', ClassName).

        `env` maps local variable names to their types for the current method.
        """
        # A name: a local variable we know, or a class name itself.
        if isinstance(e, ast.Name):
            if e.id in env:
                return env[e.id]
            if e.id in self.classes:
                return ("cls", e.id)
        elif isinstance(e, ast.Call):
            # Patient(...) creates a Patient object.
            if isinstance(e.func, ast.Name) and e.func.id in self.classes:
                return ("obj", e.func.id)
            # obj.method(...) -> use the method's return annotation.
            if isinstance(e.func, ast.Attribute):
                bt = self.type_of(e.func.value, env)
                if bt and bt[0] in ("obj", "cls"):
                    r = self.lookup(bt[1], e.func.attr)
                    if r and r[0] == "method":
                        return self.ann_type(self.classes[r[1]].methods[e.func.attr].returns)
        # obj.attr -> type of that member variable in obj's class.
        elif isinstance(e, ast.Attribute):
            bt = self.type_of(e.value, env)
            if bt and bt[0] in ("obj", "cls"):
                return self.attr_type(bt[1], e.attr)
        # items[0] -> an item of a known collection.
        elif isinstance(e, ast.Subscript):
            bt = self.type_of(e.value, env)
            if bt and bt[0] == "list":
                return ("obj", bt[1])
        return None

    def method_env(self, cname, fn):
        """Types of local names inside a method (self, annotated params, assignments, loops)."""
        env = {}
        a = fn.args
        # Annotated parameters: def treat(self, p: Patient)
        for arg in a.posonlyargs + a.args + a.kwonlyargs:
            t = self.ann_type(arg.annotation)
            if t:
                env[arg.arg] = t
        # self is an instance of this class; cls (in a classmethod) is the class.
        me = _self_name(fn)
        if me:
            env[me] = ("cls" if _is_classmethod(fn) else "obj", cname)
        # Two passes so a variable typed from another variable is still found
        # even if ast.walk reaches them in an unhelpful order.
        for _ in range(2):
            for n in ast.walk(fn):
                # p = Patient(...)   /   d = self.doctor
                if isinstance(n, ast.Assign):
                    t = self.type_of(n.value, env)
                    for tg in n.targets:
                        if t and isinstance(tg, ast.Name):
                            env[tg.id] = t
                # p: Patient = ...
                elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                    t = self.ann_type(n.annotation) or (n.value and self.type_of(n.value, env))
                    if t:
                        env[n.target.id] = t
                # for p in self.patients:   /   [p for p in self.patients]
                elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
                    t = self.type_of(n.iter, env)
                    if t and t[0] == "list" and isinstance(n.target, ast.Name):
                        env[n.target.id] = ("obj", t[1])
        return env

    # --- interactions ------------------------------------------------------
    def resolve(self, node, env):
        """Which user-defined member does `x.attr` refer to? -> (kind, owner) or None."""
        bt = self.type_of(node.value, env)
        # Known user class (or instance of one): look the member up there.
        if bt and bt[0] in ("obj", "cls"):
            return self.lookup(bt[1], node.attr)
        # A collection type (e.g. self.patients.append) is a built-in, so it's
        # skipped. Only a completely unknown receiver gets the fallback below.
        if bt is None:
            # Unknown receiver: accept it only if exactly one class has that member.
            owners = [c for c in self.classes.values()
                      if node.attr in c.methods or node.attr in c.vars]
            if len(owners) == 1:
                return self.lookup(owners[0].name, node.attr)
        return None

    def interactions(self, cname, mname):
        """Distinct things a method uses: {(kind, owner_class, name)}.

        kind is "var", "method" or "ctor" (constructing a class). It's a set,
        so each distinct thing is counted once per method.
        """
        fn, env = self.classes[cname].methods[mname], self.envs[(cname, mname)]
        found = set()
        for n in ast.walk(fn):
            # x.attr -> a member variable or method of some user class
            if isinstance(n, ast.Attribute):
                r = self.resolve(n, env)
                if r:
                    found.add((r[0], r[1], n.attr))
            # Patient(...) -> uses Patient's constructor
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id in self.classes):
                found.add(("ctor", n.func.id, "__init__"))
        return found
