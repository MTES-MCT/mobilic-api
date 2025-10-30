import boto3

from app import app
from config import MOBILIC_ENV

S3_REGION = app.config["S3_REGION"]
S3_ENDPOINT = app.config["S3_ENDPOINT"]
S3_ACCESS_KEY = app.config["S3_ACCESS_KEY"]
S3_SECRET_KEY = app.config["S3_SECRET_KEY"]

# Each env (dev,staging,prod) has its S3 bucket
BUCKET_NAME = f"mobilic-{MOBILIC_ENV}"

PRESIGNED_URLS_EXPIRY_UPLOAD_S = 60
PRESIGNED_URLS_EXPIRY_READ_S = 60


S3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
)


class S3Client:
    @staticmethod
    def nb_pictures_for_control(control_id):
        response = S3.list_objects_v2(
            Bucket=BUCKET_NAME, Prefix=f"controls/control_{str(control_id)}/"
        )

        if "Contents" not in response:
            return 0

        return len(response["Contents"])

    @staticmethod
    def list_pictures_for_control(control_id, max_nb_pictures=None):
        params = {
            "Bucket": BUCKET_NAME,
            "Prefix": f"controls/control_{str(control_id)}/",
        }
        if max_nb_pictures is not None:
            params["MaxKeys"] = max_nb_pictures

        response = S3.list_objects_v2(**params)

        if "Contents" in response:
            files = [item["Key"] for item in response["Contents"]]
            return files
        else:
            return []

    @staticmethod
    def generate_presigned_url_to_get_picture(path):
        url = S3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": path},
            ExpiresIn=PRESIGNED_URLS_EXPIRY_UPLOAD_S,  # in seconds
        )
        return url

    @staticmethod
    def generated_presigned_urls_to_upload_picture(
        control_id, nb_pictures_to_upload
    ):
        current_nb_pictures = S3Client.nb_pictures_for_control(control_id)

        presigned_urls = []
        for i in range(nb_pictures_to_upload):
            try:
                presigned_url = S3.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": BUCKET_NAME,
                        "Key": f"controls/control_{str(control_id)}/{str(i + current_nb_pictures)}.png",
                        "ACL": "public-read",
                        "ContentType": "image/png",
                    },
                    ExpiresIn=PRESIGNED_URLS_EXPIRY_READ_S,  # in seconds
                )

                presigned_urls.append(presigned_url)
            except Exception as e:
                print(f"Error {e}")

        return presigned_urls

    @staticmethod
    def upload_export(content, path, content_type):
        S3.put_object(
            Bucket=BUCKET_NAME,
            Key=path,
            Body=content,
            ContentType=content_type,
        )

    @staticmethod
    def generate_presigned_urls_exports(exports):
        from app.helpers.celery import DEFAULT_FILE_NAME

        presigned_urls = {}
        for export in exports:
            try:
                presigned_url = S3.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": BUCKET_NAME,
                        "Key": export.file_s3_path,
                        "ResponseContentDisposition": f'attachment; filename="{DEFAULT_FILE_NAME}"',
                        "ResponseContentType": export.file_type,
                    },
                    ExpiresIn=60,
                )
                presigned_urls[export.id] = presigned_url
            except Exception as e:
                print(f"Error {e}")
        return presigned_urls

    # this method can be called to allow a list of accepted origins to do some calls on the bucket
    # we have one bucket by env, so for example we can allow http://localhost:3000 for the dev bucket
    # this allows the frontend to upload an image (PUT) or see an image (GET)
    @staticmethod
    def setup_cors_configuration_for_bucket():
        cors_configuration = {
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "POST", "PUT"],
                    "AllowedOrigins": ["http://localhost:3000"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3000,
                }
            ]
        }

        S3.put_bucket_cors(
            Bucket=BUCKET_NAME, CORSConfiguration=cors_configuration
        )
