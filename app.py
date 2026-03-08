# 루트 진입점 — `streamlit run app.py` 지원
# 실제 구현은 app/main.py
import runpy, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
runpy.run_path(str(Path(__file__).parent / "app" / "main.py"), run_name="__main__")
