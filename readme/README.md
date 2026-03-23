# EIS 実装メモ

- UI起動: `py -3.11 run_ui.py` または `py -3.11 -m eis`（同一エントリ）
- **配布用 exe**: リポジトリルートで `py -3.11 tools/build.py` → `dist/eis/eis.exe`（詳細は下記「配布ビルド」）
- baseモデル更新(置換): `py -3.11 tools/update_base_model.py`
- ユーザー追加学習:
  - file: `py -3.11 tools/train_user_model.py --source-mode file --inputs "C:\path\img.jpg" --label toshiba`
  - zip: `py -3.11 tools/train_user_model.py --source-mode zip --inputs "C:\path\data.zip"`（フォルダ構造の説明は下記）

## ユーザー追加学習：ファイル指定と zip 一括（ラベルの付け方）

UI の **取り込み方式** は「ファイル指定」と「zip 一括」の2つです。**ラベル（クラス）の決め方が異なる**ため、次を押さえてください。

| 方式 | ラベル（メーカー相当クラス）の決め方 | UI の「ラベル」コンボ |
|------|----------------------------------------|------------------------|
| **ファイル指定** | 選択した画像は **すべて同じクラス**。コンボで選んだ英語クラス名（またはカタログ由来の表記）が `--label` として渡る。 | **有効**（必ず選ぶ） |
| **zip 一括** | zip 展開後、**アーカイブ内のフォルダ名**でクラスが決まる。各フォルダ名は学習用の **英語7クラス名**（`mitsubishi`, `hitachi`, `otis`, `toshiba`, `thyssenkrupp`, `westinghouse`, `montgomery`）と一致させる。該当フォルダが無い場合の挙動は CLI の `--label` フォールバックに依存（UI から zip 時は `--label` を付けない）。 | **無効**（意図的。zip 側のディレクトリでラベル付けする設計） |

- **zip で一括する場合**は、例として `data.zip` の中に `toshiba/img001.jpg` のように **クラス名フォルダの下に画像を置く**形を想定しています。単一フォルダに画像だけ詰めた zip では、UI からの学習ではクラスが定まらず取り込みに失敗しうるため、**フォルダ分け**か **ファイル指定モード＋ラベル選択**を使ってください。
- コマンドラインから zip を渡すときだけ、`tools/train_user_model.py` の `--label` を併用すると、クラス名フォルダが無い zip に対するフォールバックとして使えます（詳細は `tools/train_user_model.py` の `import_zip_mode`）。

## 配布ビルド（PyInstaller → `eis.exe`）

- **成果物名**は **`eis.exe`**（onedir: `dist/eis/`）。ルートに **`eis.py` を置かない**（パッケージ `eis` と衝突するため）。
- **公式エントリ**: `eis/__main__.py`（`python -m eis`）。PyInstaller 用は **`tools/eis_bundle_entry.py`**（`build_constants.ENTRY_SCRIPT`）。
- **ビルドの流れ**（別プロジェクト由来の **`samplebuild.py`** を参考に **`sample_build.py`** で実装）:
  1. **`dist/` と `build/` を丸ごと削除**（前回ビルドの掃除）
  2. **PyInstaller を最小 CLI** で実行: `--log-level=ERROR`、`--workpath build/pyi_work`、`--specpath build/spec_staging`、**`.spec` はビルド後に削除**
  3. **`dist/eis/` へ後からコピー**（`--add-data` で詰めすぎない）: `PACKAGE_CONTAIN_ITEMS`（既定: `tools`, `models`, `train.py`）は **`tools/build_constants.py`** で変更
  4. **`build/artifacts/` に ZIP**（`eis_<TAG>_<日時>.zip`、`TAG` は環境変数 `TAG_NAME`、未設定は `snapshot`）
- **実行コマンド**: リポジトリルートで **`py -3.11 sample_build.py`** または **`py -3.11 tools/build.py`**（中身は同じ）。
- **スモーク**: **GitHub Actions のみ自動**（`EIS_FORCE_BUILD_SMOKE=1` でローカル強制）。lite / full は `EIS_SMOKE_FULL`（従来どおり）。
- **GHA の Python**: `EIS_PY_LAUNCH=python` を推奨（`.github/workflows/build-eis.yml`）。
- **実行時パス**: フリーズ後は `eis/paths.install_root()` が **exe と同じフォルダ**。`tools/`・`models/`・`train.py` は **ビルド後コピー**で同梱。
- **コンソール**: `PYINSTALLER_CONSOLE` または **`EIS_PYI_CONSOLE=0|1`**。
- UI の学習ジョブは **`py -3.11 tools/...`** 前提のため、配布先に Python が無いと学習ボタンは動かない場合があります。

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
