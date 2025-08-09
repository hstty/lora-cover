# lora-cover (Stable Diffusion WebUI Forge - Classic)

LoRA/LyCORIS を使って生成した画像を、自動で対応する LoRA モデルの表紙 PNG に更新する拡張機能です。

- 画像保存時にプロンプトから `<lora:...>` / `<lyco:...>` タグを抽出
- 対象 LoRA（先頭/末尾/全部）を選択
- 上書き可否、正方形クロップ、最大辺サイズを設定可能
- 手動ボタンはありません（自動更新のみ）

## 使い方
1. WebUI 再起動後、Settings > LoRA Cover Auto-Update セクションを開く
2. "LoRA表紙を生成画像で自動更新" を有効にする
3. LoRA を使って画像を生成すると、対応するモデルの .png 表紙が更新されます

