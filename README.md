# SoftwareTestingAssignment2
# OO Metric Tool

A small desktop tool that calculates four object-oriented metrics for Python
classes:

- **WMC**: Weighted Methods per Class
- **Cohesion**
- **CBO**: Coupling Between Objects (per class and between each pair of classes)
- **RFC**: Response For a Class

## Requirements

- Python 3.9 or newer (3.10+ if the code you analyze uses `match` statements)
- Tkinter, which comes with the standard Python installer on Windows and macOS.
  On Linux you may need to install it, e.g. `sudo apt install python3-tk`.

## Running it

From this folder:

```
python app.py
```

## Using it

1. **Put the code in the text box**, either way:
   - paste the class definitions into the box, or
   - click **Open .py file** and pick a Python file. Its code is loaded into
     the box, where you can still edit it.
2. Click **Analyze**.
3. Read the results in the two tables (see below).
4. **Clear** empties the text box so you can analyze something else.

If the code has a syntax error, a message shows the line number and the
tables are left as they were. If there are no classes in the code, a message
says so.
