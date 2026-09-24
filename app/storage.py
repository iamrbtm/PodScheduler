import uuid
import boto3
from flask import current_app


def _client():
    return boto3.client(
        "s3",
        endpoint_url=current_app.config["MINIO_ENDPOINT"],
        aws_access_key_id=current_app.config["MINIO_ROOT_USER"],
        aws_secret_access_key=current_app.config["MINIO_ROOT_PASSWORD"],
    )


def upload_audio(file_storage, podcast_id):
    """Upload an episode audio file to the media bucket and return (object_key, public_url, file_size)."""
    ext = (file_storage.filename.rsplit(".", 1)[-1] if "." in file_storage.filename else "mp3").lower()
    object_key = f"episodes/{podcast_id}/{uuid.uuid4().hex}.{ext}"

    file_storage.stream.seek(0, 2)
    file_size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    _client().upload_fileobj(
        file_storage.stream,
        current_app.config["MINIO_BUCKET"],
        object_key,
        ExtraArgs={"ContentType": file_storage.mimetype or "audio/mpeg"},
    )

    public_url = f"{current_app.config['PUBLIC_BASE_URL']}/media/{object_key}"
    return object_key, public_url, file_size


def delete_audio(object_key):
    if not object_key:
        return
    _client().delete_object(Bucket=current_app.config["MINIO_BUCKET"], Key=object_key)
