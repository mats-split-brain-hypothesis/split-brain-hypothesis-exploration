"""Study centres: one module per study (``jlm/mu/<study>.py``), each registering its classes in
``jlm.centres.CENTRES`` on import (``CENTRES["name"] = MyCentre``). Every module here is imported when
``centres.make`` meets a name it does not know, so a new module needs no other registration.

Keeping study centres out of ``centres.py`` keeps parallel instances from editing the same file
(notes/iteration-anthony/research-loop.md, "Running several instances at once").
"""

import importlib
import pkgutil

for _m in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_m.name}")
