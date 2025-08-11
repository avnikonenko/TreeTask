"""Entry point for running the TreeTask app via ``python -m treetask``."""

from pathlib import Path
import sys
import streamlit.web.cli as stcli


def main() -> None:
    """Launch the Streamlit application.

    Streamlit's public API is geared towards running apps via the
    ``streamlit run`` command.  Attempting to bootstrap the server
    programmatically can lead to runtime errors like
    ``SessionInfo not initialized``.  To mimic the CLI behaviour we
    construct ``sys.argv`` and invoke :func:`streamlit.web.cli.main`.
    """

    app_path = Path(__file__).with_name("app.py")

    # Emulate ``streamlit run <app_path>``
    sys.argv = ["streamlit", "run", str(app_path)]
    stcli.main()


if __name__ == "__main__":
    main()
