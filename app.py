"""OO Metric Tool - paste or open Python class definitions, click Analyze."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from oo_metrics import analyze


def make_table(parent, columns, widths):
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=6)
    for col, w in zip(columns, widths):
        tree.heading(col, text=col)
        tree.column(col, width=w, anchor="w" if col in ("Class", "RFC path") else "center")
    tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    return tree


def load_file():
    """Open a .py file and put its contents in the text box."""
    path = filedialog.askopenfilename(filetypes=[("Python files", "*.py"), ("All files", "*.*")])
    if not path:                  # user pressed Cancel
        return
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        messagebox.showerror("Could not open file", str(e))
        return
    code.delete("1.0", "end")
    code.insert("1.0", text)


def run():
    try:
        result = analyze(code.get("1.0", "end"))
    except SyntaxError as e:
        messagebox.showerror("Syntax error", f"Line {e.lineno}: {e.msg}")
        return

    for table in (class_table, pair_table):
        table.delete(*table.get_children())

    if not result["classes"]:
        messagebox.showinfo("No classes", "No class definitions were found.")
        return

    for r in result["classes"]:
        hits, total, ratio = r["cohesion"]
        coh = "None" if ratio is None else f"{hits}/{total} = {ratio:.2f}"
        class_table.insert("", "end", values=(
            r["class"], r["wmc"], coh, r["cbo"],
            r["rfc_methods"], r["rfc_calls"], " -> ".join(r["rfc_path"])))

    for p in result["pairs"]:
        pair_table.insert("", "end", values=(
            p["a"], p["b"], p["a_to_b"], p["b_to_a"]))


root = tk.Tk()
root.title("OO Metric Tool")
root.geometry("1000x700")

ttk.Label(root, text="Paste Python class definitions, or open a .py file:").pack(anchor="w", padx=8, pady=(8, 0))
code = ScrolledText(root, height=16, font=("Consolas", 10), undo=True)
code.pack(fill="both", expand=True, padx=8)

buttons = ttk.Frame(root)
buttons.pack(fill="x", padx=8, pady=6)
ttk.Button(buttons, text="Analyze", command=run).pack(side="left")
ttk.Button(buttons, text="Open .py file", command=load_file).pack(side="left", padx=(6, 0))
ttk.Button(buttons, text="Clear", command=lambda: code.delete("1.0", "end")).pack(side="left", padx=6)

ttk.Label(root, text="Class metrics").pack(anchor="w", padx=8)
class_table = make_table(
    root,
    ("Class", "WMC", "Cohesion", "CBO", "RFC methods", "RFC calls", "RFC path"),
    (120, 50, 110, 50, 90, 70, 480))

ttk.Label(root, text="Coupling between pairs of classes").pack(anchor="w", padx=8)
pair_table = make_table(root, ("Class A", "Class B", "A -> B", "B -> A"), (150, 150, 80, 80))

root.mainloop()
