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
            # txt2imgタブでは常時表示のアコーディオン、img2imgでは非表示
            return scripts_module.AlwaysVisible if not is_img2img else False

        def ui(self, is_img2img):
            # txt2imgタブ用のUIアコーディオン
            import gradio as gr
            from modules import shared

            opts = shared.opts if hasattr(shared, "opts") else None
            def get_opt(name, default=None):
                return opts.data.get(name, default) if opts else default
            def set_opt(name, value):
                if opts:
                    opts.data[name] = value

            with gr.Accordion("LoRA Cover 設定", open=False):
                lora_cover_enable = gr.Checkbox(
                    label="LoRA表紙を生成画像で自動更新",
                    value=get_opt("lora_cover_enable", False)
                )
                lora_cover_target = gr.Dropdown(
                    choices=["first", "last", "all"],
                    value=get_opt("lora_cover_target", "first"),
                    label="対象LoRAの選択(先頭/末尾/全部)"
                )
                lora_cover_overwrite = gr.Checkbox(
                    label="既存の表紙があっても上書きする",
                    value=get_opt("lora_cover_overwrite", True)
                )
                lora_cover_square_crop = gr.Checkbox(
                    label="表紙を正方形にセンタークロップ",
                    value=get_opt("lora_cover_square_crop", False)
                )
                lora_cover_max_size = gr.Slider(
                    minimum=0, maximum=2048, step=1,
                    value=get_opt("lora_cover_max_size", 0),
                    label="最大辺サイズ(0で無効)"
                )

            # 値変更時にshared.optsへ反映
            lora_cover_enable.change(lambda v: set_opt("lora_cover_enable", v), lora_cover_enable, None)
            lora_cover_target.change(lambda v: set_opt("lora_cover_target", v), lora_cover_target, None)
            lora_cover_overwrite.change(lambda v: set_opt("lora_cover_overwrite", v), lora_cover_overwrite, None)
            lora_cover_square_crop.change(lambda v: set_opt("lora_cover_square_crop", v), lora_cover_square_crop, None)
            lora_cover_max_size.change(lambda v: set_opt("lora_cover_max_size", v), lora_cover_max_size, None)
            return [lora_cover_enable, lora_cover_target, lora_cover_overwrite, lora_cover_square_crop, lora_cover_max_size]
except Exception:
    pass
