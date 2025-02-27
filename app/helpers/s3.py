import boto3

from app import app
from config import MOBILIC_ENV

SCW_REGION = app.config["SCW_REGION"]
SCW_ENDPOINT = app.config["SCW_ENDPOINT"]
SCW_ACCESS_KEY = app.config["SCW_ACCESS_KEY"]
SCW_SECRET_KEY = app.config["SCW_SECRET_KEY"]

# Each env (dev,staging,prod) has its S3 bucket
BUCKET_NAME = f"mobilic-{MOBILIC_ENV}"

PRESIGNED_URLS_EXPIRY_UPLOAD_S = 60
PRESIGNED_URLS_EXPIRY_READ_S = 60


S3 = boto3.client(
    "s3",
    endpoint_url=SCW_ENDPOINT,
    aws_access_key_id=SCW_ACCESS_KEY,
    aws_secret_access_key=SCW_SECRET_KEY,
)


class S3Client:
    @staticmethod
    def nb_pictures_for_control(control_id):
        response = S3.list_objects_v2(
            Bucket=BUCKET_NAME, Prefix=f"controls/control_{str(control_id)}/"
        )

        if "Contents" not in response:
            return 0

        # folder itself is counted as an item
        return len(response["Contents"]) - 1

    @staticmethod
    def list_pictures_for_control(control_id, max_nb_pictures=3):
        response = S3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=f"controls/control_{str(control_id)}/",
            MaxKeys=max_nb_pictures,
        )

        if "Contents" in response:
            files = [item["Key"] for item in response["Contents"]]
            return files
        else:
            return []

    # generate presigned urls for the front to see picture
    @staticmethod
    def generate_presigned_url_for_picture(path):
        url = S3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": path},
            ExpiresIn=PRESIGNED_URLS_EXPIRY_UPLOAD_S,  # in seconds
        )
        return url

    # generate presigned urls for the front to upload pictures to the bucket
    @staticmethod
    def generated_presigned_urls_for_control(
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
