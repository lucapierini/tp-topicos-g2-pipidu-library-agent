"""Sube rag/documents/pdf/*.pdf al bucket privado `rag` de Neon Object Storage.

Credenciales y endpoint salen de .env.local (AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY, AWS_ENDPOINT_URL_S3, AWS_REGION).
Es idempotente: sobrescribe la misma clave `documents/<archivo>.pdf`.
"""
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "documents" / "pdf"
BUCKET = "rag"
PREFIX = "documents/"


def s3_client():
    load_dotenv(ROOT.parent / ".env.local")
    # Neon exige path-style y SigV4; endpoint/región/credenciales vienen del entorno AWS_*.
    import os
    return boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        region_name=os.environ["AWS_REGION"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def main():
    s3 = s3_client()
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        key = PREFIX + pdf.name
        s3.upload_file(str(pdf), BUCKET, key, ExtraArgs={"ContentType": "application/pdf"})
        print(f"subido {key} ({pdf.stat().st_size} bytes)")
    listed = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX).get("Contents", [])
    print(f"en el bucket '{BUCKET}': {len(listed)} objetos")


if __name__ == "__main__":
    main()
