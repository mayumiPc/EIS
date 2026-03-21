# EIS 実装メモ

- UI起動: `py -3.11 run_ui.py`
- baseモデル更新(置換): `py -3.11 tools/update_base_model.py`
- ユーザー追加学習:
  - file: `py -3.11 tools/train_user_model.py --source-mode file --inputs "C:\path\img.jpg" --label toshiba`
  - zip: `py -3.11 tools/train_user_model.py --source-mode zip --inputs "C:\path\data.zip"`

用途推薦は `推論のみ実行` と `用途推薦を実行` を分離しています。  
用途の自由入力（複数行）を推薦に反映します。

