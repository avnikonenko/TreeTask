"""Entry point for running the TreeTask app via ``python -m treetask``."""

from pathlib import Path
import streamlit.web.bootstrap


def main() -> None:
    app_path = Path(__file__).with_name("app.py")
    streamlit.web.bootstrap.run(str(app_path), "", [], {})


if __name__ == "__main__":
    main()
