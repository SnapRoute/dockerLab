# import all labs packages and provide importable list
import os, imp

ldir = os.path.dirname(os.path.realpath(__file__))
unsorted_labs = {}
for fm in os.listdir(ldir):
    if os.path.isdir("%s/%s" % (ldir, fm)):
        try:
            f, fname, desc = imp.find_module(fm, [ldir])
            mod = imp.load_module("%s" % fm, f, fname, desc)
            # ensure module has correctly formated docstring
            if mod.__doc__ is None: mod.__doc__ = ""
            lines = mod.__doc__.strip().split("\n")
            if ":" not in lines[0]: lines[0] = "%s: %s" % (fm, fm)
            if len(lines)==1: lines.append("")
            mod.__doc__ = "\n".join(lines) 
            unsorted_labs[fm] = mod
        except ImportError as e: pass

labs = []
for fm in sorted(unsorted_labs.keys()):
    labs.append(unsorted_labs[fm])

