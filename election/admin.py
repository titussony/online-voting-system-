from django.contrib import admin

from .models import (
    Election,
    Candidate,
    Vote,
    VoteOTP,
    ElectionEligibleVoter,
)


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'status',
        'eligibility_type',
        'start_date',
        'end_date',
        'results_published',
    )

    list_filter = (
        'status',
        'eligibility_type',
        'results_published',
    )

    search_fields = (
        'name',
        'description',
    )


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'election',
        'party',
        'created_at',
    )

    list_filter = (
        'election',
    )

    search_fields = (
        'name',
        'party',
        'election__name',
    )


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):

    list_display = (
        'voter',
        'election',
        'candidate',
        'voted_at',
    )

    list_filter = (
        'election',
        'candidate',
    )

    search_fields = (
        'voter__username',
        'election__name',
        'candidate__name',
    )


@admin.register(VoteOTP)
class VoteOTPAdmin(admin.ModelAdmin):

    list_display = (
        'voter',
        'election',
        'candidate',
        'otp',
        'created_at',
        'is_used',
    )

    list_filter = (
        'election',
        'is_used',
    )

    search_fields = (
        'voter__username',
        'election__name',
    )


@admin.register(ElectionEligibleVoter)
class ElectionEligibleVoterAdmin(admin.ModelAdmin):

    list_display = (
        'election',
        'aadhaar_number',
        'added_at',
    )

    list_filter = (
        'election',
    )

    search_fields = (
        'aadhaar_number',
        'election__name',
    )