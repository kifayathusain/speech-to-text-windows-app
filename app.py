"""Desktop entry point for the Windows TTS App (M02).

Launches the Tkinter desktop UI. The UI reuses the same service layer as
the CLI (``main.py``) — see ``ttsapp/gui.py`` and ``ttsapp/service.py``.

Usage:

    python app.py
"""

import sys

from ttsapp.runtime_paths import configure_bundled_media


def main() -> int:
    """Launch the desktop, or explicitly requested portable-package diagnostics."""
    if "--diagnostics" in sys.argv:
        from ttsapp.diagnostics import main

        return main(sys.argv[1:])
    try:
        configure_bundled_media()
    except (OSError, ValueError):
        from tkinter import messagebox

        messagebox.showerror(
            "Windows TTS App",
            "Packaged media tools are missing or failed integrity verification. "
            "Extract the complete original ZIP again before launching the app.",
        )
        return 1
    from ttsapp.gui import main

    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
