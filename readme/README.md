# EIS 実装メモ

- UI起動: `py -3.11 run_ui.py`
- baseモデル更新(置換): `py -3.11 tools/update_base_model.py`
- ユーザー追加学習:
  - file: `py -3.11 tools/train_user_model.py --source-mode file --inputs "C:\path\img.jpg" --label toshiba`
  - zip: `py -3.11 tools/train_user_model.py --source-mode zip --inputs "C:\path\data.zip"`

画面の中心は **設置カタログ**（内部 SQLite。元データは Access `.accdb` から取り込み）です。プルダウンを変えると一覧が自動更新されます。  
**推論を実行** 後は、推論結果に加え **テンプレート列（メーカー・種類・所在地・設置名称・メディアパス等）を入力して内部カタログへ登録**できるダイアログが開きます（メーカーと設置名称は必須）。内部カタログ未作成時は登録ボタンは無効です。
用途推薦・読み取り専用の結果ログ・用途の手動入力は廃止し、詳細ログは `EIS.log` です。

## 初期化メニュー（ユーザー学習のリセット）

- **初期化 → ユーザー学習データのリセット(危険)** は、確認ダイアログを **3回（文言はそれぞれ別）** 出したうえで、次のみ削除します: `models/eis_classifier_user.pt`、`dataset_user/`、`dataset_combined_user/`。
- 初回モデル・`dataset/`・`dataset_legacy/`・内部カタログ・`.accdb` 等は削除しません。学習ジョブ実行中は利用できません。

## 設置カタログ（内部 DB と Access 取り込み）

- **起動時**: `run_ui.py` は **先に** `data/eis_installation_catalog.sqlite.next`（取り込み仮ファイル）があれば、本体 `eis_installation_catalog.sqlite` へ差し替えます（このとき他プロセスが本体を開いていない状態です）。
- **初回／カタログDBの更新**: Access `.accdb` を選ぶと **仮ファイル `.sqlite.next` のみ** が更新されたうえで、**アプリが同じコマンドラインで自動再起動**します。起動直後に `.next` が本体 `.sqlite` に取り込まれ、一覧に反映されます（実行中に本体を差し替えないためロック問題を避けます）。
- **ファイル → カタログDBの更新…** でも同じフローです。
- 一覧の絞り込みは **メーカー・種類・都道府県・市区町村・用途(DB)・積載・定員**（検索ボタンはありません）。実行中は内部 SQLite のみを参照し、`.accdb` を直接開きません。
- 行を選び **選択行を作業に反映** で学習ラベル（英語クラス名）を更新します。実ファイルパスと解釈できる場合のみメディアパスも設定されます。
- **取り込み時のみ** `pyodbc` と **Microsoft Access Database Engine (ACE)** の ODBC ドライバが必要です（内部カタログ作成・更新のとき）。
- スキーマ・列マッピングは `eis/catalog_template.py` を参照（将来の仕様変更はここと取り込み処理を更新）。
- **テンプレート取り込みが「保証する」範囲**: 実行時に読むのは内部 SQLite のみ（`eis/catalog_sqlite.py`）。Access は `eis/catalog_import_access.py` で**取り込み実行時だけ** `pyodbc` 接続する。取り込み時に **テーブル「設置場所」** と **必須列**（`catalog_template.ACCESS_COLUMNS_REQUIRED`）の存在を検証し、行データをテンプレート列へ写す。Access 側の全機能・全オブジェクト型の完全再現や、業務ルールの正しさまで保証するもの**ではない**（不正データは取り込みエラーまたは文字列化等になる）。
- **「設置場所」の .accdb をプロジェクトから削除してよいか**: **`data/eis_installation_catalog.sqlite` が有効に生成・反映済み**であれば、**アプリの通常利用（一覧・検索・作業反映）には元の .accdb は不要**。ただし **ファイル → カタログDBの更新** で再取り込みする場合は、**どこか別の場所に置いた .accdb** が再度必要。唯一のマスタを消すと再取得できなくなるため、必要に応じてバックアップを推奨。
- 初回学習モデル・画像取得: `tools/` の学習スクリプト、`pixabay-downloader` 等は従来どおり利用できます。
