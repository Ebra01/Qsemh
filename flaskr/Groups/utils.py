import os
from flaskr.utils import s3, s3_resource
from flaskr.Models.models import Files


BUCKET = os.getenv('S3_BUCKET')


# AWS S3
def upload_images(img):
    """
    Upload An Image To AWS S3
    """

    my_bucket = s3_resource.Bucket(BUCKET)

    filename = img.filename

    if filename == '':
        raise Exception('No File Uploaded')

    try:
        new_file = Files(filename)
        new_file.insert()
        filename = new_file.file_name
    except Exception as e:
        print(e)

    try:
        my_bucket.Object(filename).put(Body=img)
    except Exception as e:
        print(e)
        raise Exception('Error While Uploading Image')

    return filename


def delete_images(img):
    """
    Delete An Image To AWS S3
    """

    my_bucket = s3_resource.Bucket(BUCKET)

    try:
        my_bucket.Object(img).delete()
    except Exception as e:
        print(e)
        raise Exception('Error While Uploading Image')


def download_images(key, expire=90):
    if not key:
        return None

    try:
        return s3.generate_presigned_url('get_object',
                                         Params={'Bucket': BUCKET, 'Key': key},
                                         ExpiresIn=expire)
    except Exception as e:
        print(e)
        raise Exception('Error While Uploading Image')

