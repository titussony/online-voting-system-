from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


# =========================================================
# EMAIL OTP
# =========================================================

class EmailOTP(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_otps'
    )

    otp = models.CharField(
        max_length=6
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    is_used = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f"OTP for {self.user.username}"


# =========================================================
# VOTER
# =========================================================

class Voter(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='voter_profile'
    )

    full_name = models.CharField(
        max_length=150
    )

    phone = models.CharField(
        max_length=15
    )

    aadhaar_number = models.CharField(
        max_length=5,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{5}$',
                message='Aadhaar number must contain exactly 5 digits.'
            )
        ]
    )

    voter_id = models.CharField(
        max_length=20,
        unique=True
    )

    date_of_birth = models.DateField()

    address = models.TextField()

    photo = models.ImageField(
        upload_to='voters/',
        blank=True,
        null=True
    )

    is_verified = models.BooleanField(
        default=False
    )

    email_verified = models.BooleanField(
        default=False
    )

    face_verified = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.full_name


# =========================================================
# APPROVED VOTER
# =========================================================

class ApprovedVoter(models.Model):

    aadhaar_number = models.CharField(
        max_length=5,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{5}$',
                message='Aadhaar number must contain exactly 5 digits.'
            )
        ]
    )

    full_name = models.CharField(
        max_length=150
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.aadhaar_number} - {self.full_name}"