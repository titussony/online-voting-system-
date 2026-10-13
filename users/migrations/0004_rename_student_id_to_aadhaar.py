from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_approvedvoter'),
    ]

    operations = [
        migrations.RenameField(
            model_name='approvedvoter',
            old_name='student_id',
            new_name='aadhaar_number',
        ),
    ]