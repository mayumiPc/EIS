# EIS Quick Notes

- Run UI: `py -3.11 run_ui.py`
- Update/replace base model: `py -3.11 tools/update_base_model.py`
- Train user model:
  - file: `py -3.11 tools/train_user_model.py --source-mode file --inputs "C:\path\img.jpg" --label toshiba`
  - zip: `py -3.11 tools/train_user_model.py --source-mode zip --inputs "C:\path\data.zip"`

Inference and recommendation are separated in UI.  
Use-case free-text (multiline) is included in recommendation.

