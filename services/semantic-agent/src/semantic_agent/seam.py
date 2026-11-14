"""One way to choose a seam's implementation from the environment (semantic/PLAN.md SL-19).

A seam is a module `<seam>.py` holding the interface and a module `<seam>_<impl>.py` per
implementation; an environment variable names the implementation, and only the chosen module, with
its dependencies, is imported, so an image carries only what it runs. `choose` is that selection,
shared by every seam (`AGENT_WAREHOUSE` in warehouse.py, `AGENT_TOOLSET` in toolset.py) so each
refuses an unknown name and names the extra a missing dependency needs the same way.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from types import ModuleType


def choose(
    variable: str,
    implementations: Mapping[str, str],
    *,
    default: str,
    extras: Mapping[str, str] | None = None,
    error: type[Exception] = ValueError,
) -> ModuleType:
    """The implementation module `variable` names (`default` when unset), imported only now.

    `implementations` maps each name to its module; `extras` names the extra of semantic-agent that
    installs an implementation's dependencies. An unknown name, or a module whose dependencies are
    not installed, raises `error` saying which names exist or which extra to install.
    """
    name = os.environ.get(variable) or default
    if name not in implementations:
        raise error(f"{variable}={name!r} is not one of {', '.join(sorted(implementations))}")
    try:
        return importlib.import_module(implementations[name])
    except ImportError as e:
        extra = (extras or {}).get(name)
        needs = f"the {extra!r} extra of semantic-agent" if extra else "a missing dependency"
        raise error(f"{variable}={name} needs {needs} ({e})") from e
