"""
Loader script for Stable Diffusion WebUI Forge/A1111 scripts discovery.
Ensures the extension module (now placed under scripts/) is imported so
settings and callbacks register. Avoid importing as 'scripts.lora_cover'
to prevent name conflicts with other 'scripts' modules; instead extend sys.path
to include this directory and import 'lora_cover' directly.
"""

import os
import sys


def _import_extension_module():
    this_dir = os.path.dirname(__file__)
    if this_dir not in sys.path:
        sys.path.insert(0, this_dir)
    try:
        import lora_cover  # noqa: F401 - side effects register settings/callbacks
    except Exception as e:
        print(f"[lora-cover] loader import error: {e}")


_import_extension_module()

# Optional: Define a hidden Script so the loader is recognized by the scripts system
try:  # pragma: no cover
    from modules import scripts as scripts_module  # type: ignore

    class Script(scripts_module.Script):  # type: ignore
        def title(self):
            return "LoRA Cover Auto-Update (loader)"

        def show(self, is_img2img):
            # Hide this from UI tabs; the functionality is callback-based
            return False
except Exception:
    pass
