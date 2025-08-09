"""
LoRA Cover Auto-Updater for Stable Diffusion WebUI Forge - Classic

機能:
- 画像保存時に使用された LoRA/LyCORIS を検出し、対応するモデルの表紙画像(カード)を
	生成画像で自動更新します。

この拡張は設定による自動更新のみを提供します（手動ボタンはありません）。
"""

import os
import re
from typing import List, Optional

try:
	import gradio as gr  # type: ignore
except Exception:  # pragma: no cover - UIが無い環境向け
	gr = None  # type: ignore

from PIL import Image
from PIL.Image import Image as PILImage

try:
	from modules import script_callbacks  # type: ignore
	from modules import shared  # type: ignore
except Exception as e:  # pragma: no cover
	# 実行時に WebUI 環境外だと import に失敗する可能性がある
	script_callbacks = None  # type: ignore
	shared = None  # type: ignore


SECTION_KEY = "lora_cover"
SECTION_LABEL = "LoRA Cover Auto-Update"
SECTION_ID = (SECTION_KEY, SECTION_LABEL)


def _get_models_root() -> Optional[str]:
	"""models ルートパスを可能な範囲で推測して返す。"""
	# Forge/A1111 での既定
	try:
		from modules.paths_internal import models_path  # type: ignore
		if models_path:
			return models_path
	except Exception:
		pass

	try:
		from modules import paths  # type: ignore
		models_path = getattr(paths, "models_path", None)
		if models_path:
			return models_path
	except Exception:
		pass

	return None


def _candidate_lora_dirs() -> List[str]:
	"""LoRA/LyCORIS の候補ディレクトリ一覧を返す。"""
	dirs: List[str] = []

	if shared is not None:
		# 明示指定(起動オプション/設定)の優先
		cmd = getattr(shared, "cmd_opts", None)
		if cmd is not None:
			d = getattr(cmd, "lora_dir", None)
			if d:
				dirs.append(d)

		opts = getattr(shared, "opts", None)
		data = getattr(opts, "data", {}) if opts is not None else {}
		for key in ("lora_dir", "lyco_dir", "lycoris_dir"):
			d = data.get(key)
			if d:
				dirs.append(d)

	# 既定の models/Lora, models/LyCORIS
	models_root = _get_models_root()
	if models_root:
		for sub in ("Lora", "LyCORIS", "LoRA", "lycoris"):
			d = os.path.join(models_root, sub)
			if os.path.isdir(d):
				dirs.append(d)

	# 正規化 + 重複排除
	normed = []
	seen = set()
	for d in dirs:
		nd = os.path.abspath(d)
		if nd not in seen:
			seen.add(nd)
			normed.append(nd)
	return normed


def _get_outputs_dirs(mode: Optional[str] = None) -> List[str]:
	dirs: List[str] = []
	try:
		if shared is not None and getattr(shared, "opts", None) is not None:
			data = getattr(shared.opts, "data", {})
			keys = []
			if mode == "t2i":
				keys = [
					"outdir_txt2img_samples",
					"outdir_txt2img_grids",
					"outdir_saving_images",
				]
			elif mode == "i2i":
				keys = [
					"outdir_img2img_samples",
					"outdir_img2img_grids",
					"outdir_saving_images",
				]
			else:
				keys = [
					"outdir_txt2img_samples",
					"outdir_txt2img_grids",
					"outdir_img2img_samples",
					"outdir_img2img_grids",
					"outdir_saving_images",
				]
			for k in keys:
				d = data.get(k)
				if d:
					dirs.append(d)
	except Exception:
		pass
	# generic outputs fallback
	try:
		base = None
		try:
			from modules.paths_internal import script_path  # type: ignore
			base = script_path
		except Exception:
			try:
				from modules import paths  # type: ignore
				base = getattr(paths, "script_path", None)
			except Exception:
				base = None
		if base:
			out = os.path.join(base, "outputs")
			if os.path.isdir(out):
				dirs.append(out)
	except Exception:
		pass
	# normalize unique
	normed: List[str] = []
	seen = set()
	for d in dirs:
		nd = os.path.abspath(d)
		if nd not in seen and os.path.isdir(nd):
			seen.add(nd)
			normed.append(nd)
	return normed


def _search_file_in_dirs(filename: str, dirs: List[str]) -> Optional[str]:
	try:
		base = os.path.basename(filename)
		for root in dirs:
			for dirpath, _, files in os.walk(root):
				for fn in files:
					if fn == base:
						return os.path.join(dirpath, fn)
	except Exception:
		pass
	return None


def _find_lora_file(name: str) -> Optional[str]:
	"""LoRA/LyCORIS モデルファイルを名前から探索する。

	name は通常、拡張子無しのベース名(サブディレクトリを含む場合あり)。
	優先度: 相対パス一致 -> 再帰探索でベース名一致。
	対応拡張子: .safetensors, .pt, .ckpt
	"""
	if not name:
		return None

	name = name.strip().replace("\\", "/")
	exts = (".safetensors", ".pt", ".ckpt")
	base = os.path.basename(name)
	rel = name if "/" in name else None

	for root in _candidate_lora_dirs():
		# 相対パス指定の直接一致
		if rel:
			# 拡張子付き/無しの両対応
			if os.path.splitext(rel)[1].lower() in exts:
				p = os.path.join(root, rel)
				if os.path.isfile(p):
					return p
			else:
				for ext in exts:
					p = os.path.join(root, rel + ext)
					if os.path.isfile(p):
						return p

		# 再帰探索でベース名一致
		for dirpath, _, files in os.walk(root):
			for fn in files:
				ext = os.path.splitext(fn)[1].lower()
				if ext in exts and os.path.splitext(fn)[0].lower() == base.lower():
					return os.path.join(dirpath, fn)

	return None


_TAG_RE = re.compile(r"<(?:lora|lyco):([^:>]+)(?::[^>]+)?>", re.IGNORECASE)


def _extract_lora_names(texts: List[str]) -> List[str]:
	names: List[str] = []
	for t in texts:
		if not t:
			continue
		for m in _TAG_RE.finditer(t):
			n = (m.group(1) or "").strip()
			if n:
				names.append(n)
	# 順序維持の重複排除
	seen = set()
	uniq: List[str] = []
	for n in names:
		k = n.lower()
		if k not in seen:
			seen.add(k)
			uniq.append(n)
	return uniq


def _center_square_crop(img: PILImage) -> PILImage:
	w, h = img.size
	if w == h:
		return img
	side = min(w, h)
	left = (w - side) // 2
	top = (h - side) // 2
	return img.crop((left, top, left + side, top + side))


def _prepare_cover(img: PILImage, square_crop: bool, max_size: int) -> PILImage:
	# 透過等を避けるため RGB 固定
	if img.mode not in ("RGB",):
		img = img.convert("RGB")
	if square_crop:
		img = _center_square_crop(img)
	if isinstance(max_size, int) and max_size > 0:
		w, h = img.size
		if max(w, h) > max_size:
			if w >= h:
				new_w = max_size
				new_h = int(h * (max_size / w))
			else:
				new_h = max_size
				new_w = int(w * (max_size / h))
			img = img.resize((new_w, new_h), Image.LANCZOS)
	return img


def _build_pnginfo(params) -> Optional[object]:
	# PIL の PngInfo を可能なら作って parameters を保存
	try:
		from PIL.PngImagePlugin import PngInfo  # type: ignore
		pi = PngInfo()
		info_text = None
		if hasattr(params, "pnginfo") and params.pnginfo:
			info_text = params.pnginfo.get("parameters") or params.pnginfo.get("prompt")
		if not info_text and hasattr(params, "infotext"):
			info_text = getattr(params, "infotext")
		if info_text:
			pi.add_text("parameters", str(info_text))
		return pi
	except Exception:
		return None


def _get_opt(name: str, default=None):
	if shared is None or getattr(shared, "opts", None) is None:
		return default
	try:
		return shared.opts.data.get(name, default)
	except Exception:
		return default


def _save_cover_for_targets(image: PILImage, params, targets: List[str]):
	overwrite = bool(_get_opt("lora_cover_overwrite", True))
	square_crop = bool(_get_opt("lora_cover_square_crop", False))
	max_size = int(_get_opt("lora_cover_max_size", 0) or 0)
	pnginfo = _build_pnginfo(params)

	for name in targets:
		model_file = _find_lora_file(name)
		if not model_file:
			print(f"[lora-cover] model not found for '{name}'")
			continue
		base, _ = os.path.splitext(model_file)
		cover_path = base + ".png"

		if (not overwrite) and os.path.exists(cover_path):
			# 既存カバーがあればスキップ
			continue

		try:
			os.makedirs(os.path.dirname(cover_path), exist_ok=True)
			out = _prepare_cover(image, square_crop, max_size)
			out.save(cover_path, format="PNG", pnginfo=pnginfo)
			print(f"[lora-cover] updated cover: {os.path.basename(cover_path)}")
		except Exception as e:
			print(f"[lora-cover] failed to save cover for '{name}': {e}")


def on_image_saved(params):  # script_callbacks.ImageSaveParams 想定
	try:
		p = getattr(params, "p", None)
		if p is None:
			return

		if not bool(_get_opt("lora_cover_enable", False)):
			return

		texts: List[str] = []
		for attr in ("prompt", "negative_prompt"):
			v = getattr(p, attr, None)
			if v:
				texts.append(str(v))

		names = _extract_lora_names(texts)
		if not names:
			return

		target_mode = str(_get_opt("lora_cover_target", "first") or "first").lower()
		if target_mode == "last":
			targets = [names[-1]]
		elif target_mode == "all":
			targets = names
		else:  # first
			targets = [names[0]]

		_save_cover_for_targets(params.image, params, targets)
	except Exception as e:
		print(f"[lora-cover] on_image_saved error: {e}")


def _register_options():
	if shared is None:
		return
	try:
		from modules.shared import OptionInfo  # type: ignore
	except Exception:
		return

	# セクション作成APIがあれば先に作成
	try:
		add_section = getattr(shared.opts, "add_section", None)
		if callable(add_section):
			add_section(SECTION_KEY, SECTION_LABEL)
	except Exception:
		pass

	# UI コンポーネントが利用不可でも最低限の登録は試行
	def _comp_checkbox():
		return gr.Checkbox if gr is not None else None

	def _comp_dropdown():
		return gr.Dropdown if gr is not None else None

	def _comp_slider():
		return gr.Slider if gr is not None else None

	try:
		shared.opts.add_option(
			"lora_cover_enable",
			OptionInfo(False, "LoRA表紙を生成画像で自動更新", _comp_checkbox(), section=SECTION_ID),
		)
		shared.opts.add_option(
			"lora_cover_target",
			OptionInfo(
				"first",
				"対象LoRAの選択(先頭/末尾/全部)",
				 _comp_dropdown(),
				{"choices": ["first", "last", "all"]},
				section=SECTION_ID,
			),
		)
		shared.opts.add_option(
			"lora_cover_overwrite",
			OptionInfo(True, "既存の表紙があっても上書きする", _comp_checkbox(), section=SECTION_ID),
		)
		shared.opts.add_option(
			"lora_cover_square_crop",
			OptionInfo(False, "表紙を正方形にセンタークロップ", _comp_checkbox(), section=SECTION_ID),
		)
		shared.opts.add_option(
			"lora_cover_max_size",
			OptionInfo(
				0,
				"最大辺サイズ(0で無効)",
				 _comp_slider(),
				{"minimum": 0, "maximum": 2048, "step": 1},
				section=SECTION_ID,
			),
		)
		print("[lora-cover] settings registered")
	except Exception as e:
		print(f"[lora-cover] failed to register settings: {e}")


def on_ui_settings():
	# UI構築タイミングでも再登録を試みる（安全）
	_register_options()


def _register_callbacks():
	if script_callbacks is None:
		return
	try:
		script_callbacks.on_image_saved(on_image_saved)
	except Exception as e:
		print(f"[lora-cover] failed to register on_image_saved: {e}")
	try:
		script_callbacks.on_ui_settings(on_ui_settings)
	except Exception as e:
		print(f"[lora-cover] failed to register on_ui_settings: {e}")
	# 手動UIなし


# import 時に設定とコールバックを登録
_register_options()
_register_callbacks()
