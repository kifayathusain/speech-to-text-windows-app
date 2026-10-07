"""Application/service layer for the Windows TTS app.

This package separates concerns so a future desktop UI can reuse the same
generation pipeline that the CLI entry point (``main.py``) uses:

    UI
     v
    ttsapp.service        (application/service layer)
     v
    ttsapp.parser         (conversation script -> structured lines)
    ttsapp.tts_engine     (Microsoft Edge TTS adapter)
    ttsapp.audio_combiner (FFmpeg adapter)
     v
    filesystem/output
"""
