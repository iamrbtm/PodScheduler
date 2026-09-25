from mutagen import File as MutagenFile


def get_duration_seconds(file_storage):
    file_storage.stream.seek(0)
    try:
        audio = MutagenFile(file_storage.stream)
    except Exception:
        audio = None
    file_storage.stream.seek(0)

    if audio is not None and audio.info is not None:
        return int(audio.info.length)
    return None
