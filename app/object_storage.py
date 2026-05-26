import os


def storage_backend(env_name: str, default: str = "local") -> str:
    return os.getenv(env_name, default).strip().lower()


def put_object(key: str, content: bytes, content_type: str | None = None) -> None:
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    _s3_client().put_object(Bucket=bucket_name(), Key=key, Body=content, **extra_args)


def get_object_bytes(key: str) -> bytes:
    response = _s3_client().get_object(Bucket=bucket_name(), Key=key)
    return response["Body"].read()


def delete_object(key: str | None) -> None:
    if not key:
        return
    _s3_client().delete_object(Bucket=bucket_name(), Key=key)


def list_objects(
    *,
    prefix: str = "",
    continuation_token: str | None = None,
    max_keys: int = 100,
) -> dict:
    params = {
        "Bucket": bucket_name(),
        "MaxKeys": max(1, min(max_keys, 1000)),
    }
    if prefix:
        params["Prefix"] = prefix
    if continuation_token:
        params["ContinuationToken"] = continuation_token
    response = _s3_client().list_objects_v2(**params)
    return {
        "objects": response.get("Contents", []) or [],
        "next_cursor": response.get("NextContinuationToken"),
        "is_truncated": bool(response.get("IsTruncated")),
    }


def head_object_metadata(key: str) -> dict:
    return _s3_client().head_object(Bucket=bucket_name(), Key=key)


def presigned_get_url(
    key: str,
    *,
    content_disposition: str | None = None,
    ttl_seconds: int | None = None,
) -> str:
    params = {"Bucket": bucket_name(), "Key": key}
    if content_disposition:
        params["ResponseContentDisposition"] = content_disposition
    return _s3_client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=ttl_seconds if ttl_seconds is not None else signed_url_ttl_seconds(),
    )


def signed_url_ttl_seconds() -> int:
    return int(os.getenv("HETZNER_S3_SIGNED_URL_TTL_SECONDS", "600"))


def bucket_name() -> str:
    return _required_env("HETZNER_S3_BUCKET")


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=_required_env("HETZNER_S3_ENDPOINT_URL"),
        region_name=os.getenv("HETZNER_S3_REGION", "fsn1"),
        aws_access_key_id=_required_env("HETZNER_S3_ACCESS_KEY_ID"),
        aws_secret_access_key=_required_env("HETZNER_S3_SECRET_ACCESS_KEY"),
    )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for object storage")
    return value
