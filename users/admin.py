from django.contrib import admin

from .models import Voter, EmailOTP, ApprovedVoter


# ==================================================
# VOTER
# ==================================================

@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):

    list_display = (
        'full_name',
        'voter_id',
        'aadhaar_number',
        'phone',
        'is_verified',
        'is_active',
        'created_at',
    )

    list_filter = (
        'is_verified',
        'is_active',
    )

    search_fields = (
        'full_name',
        'voter_id',
        'aadhaar_number',
        'phone',
        'user__username',
    )


# ==================================================
# EMAIL OTP
# ==================================================

@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):

    list_display = (
        'user',
        'otp',
        'created_at',
        'is_used',
    )

    list_filter = (
        'is_used',
    )

    search_fields = (
        'user__username',
    )


# ==================================================
# APPROVED VOTER
# ==================================================

@admin.register(ApprovedVoter)
class ApprovedVoterAdmin(admin.ModelAdmin):

    list_display = (
        'aadhaar_number',
        'full_name',
        'email',
        'date_of_birth',
        'is_active',
        'created_at',
    )

    list_filter = (
        'is_active',
    )

    search_fields = (
        'aadhaar_number',
        'full_name',
        'email',
    )