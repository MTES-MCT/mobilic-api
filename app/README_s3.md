# S3 Setup

## Why a S3 ?

We started using a S3 in march 2025 because we wanted `ControllerUser` to be able to take pictures and attach them to `Controls`.

## Initial setup

We decided to use Scaleway's Object Storage feature.
We have one bucket per env (dev, staging, prod) `mobilic-[env]`

## Implementation

A file `app/helpers/s3.py` in which we create a S3 client with `boto3` lib. We define static methods in a `S3Client` class to expose features.
Some ENV variables are introduced:

```
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_REGION=
S3_ENDPOINT=
```

### Control pictures
Inside each bucket, we have a folder named `controls`.
In this folder, each `Control` will have its folder named `control_[control_id]` in which all pictures will be stored (named `0.png`, `1.png`, ...)

#### Allowing origins url to buckets

Snippet to allow `http://localhost:3000` to do actions on the dev bucket (it's needed to get the pictures and to upload them)
```
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
            Bucket=mobilic-dev, CORSConfiguration=cors_configuration
        )
```
