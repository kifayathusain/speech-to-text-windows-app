"""Desktop entry point for the Windows TTS App (M02).

Launches the Tkinter desktop UI. The UI reuses the same service layer as
the CLI (``main.py``) — see ``ttsapp/gui.py`` and ``ttsapp/service.py``.

Usage:

    python app.py
"""

from ttsapp.gui import main

if __name__ == "__main__":
    main()
