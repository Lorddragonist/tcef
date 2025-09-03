# Generated manually to rename GCP fields to S3 fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0002_passwordresetapproval_userapprovalrequest'),
    ]

    operations = [
        migrations.RenameField(
            model_name='videouploadsession',
            old_name='gcp_bucket',
            new_name='s3_bucket',
        ),
        migrations.RenameField(
            model_name='videouploadsession',
            old_name='gcp_blob_name',
            new_name='s3_key',
        ),
    ] 