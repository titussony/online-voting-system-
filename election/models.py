from django.db import models
from django.contrib.auth.models import User


class Election(models.Model):

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('UPCOMING', 'Upcoming'),
        ('ONGOING', 'Ongoing'),
        ('CLOSED', 'Closed'),
    ]

    ELIGIBILITY_CHOICES = [
        ('EVERYONE', 'Everyone'),
        ('SELECTED', 'Selected Aadhaar Numbers'),
    ]

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )

    eligibility_type = models.CharField(
        max_length=20,
        choices=ELIGIBILITY_CHOICES,
        default='EVERYONE'
    )

    results_published = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name


class Candidate(models.Model):

    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name='candidates'
    )

    name = models.CharField(
        max_length=150
    )

    party = models.CharField(
        max_length=150,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    photo = models.ImageField(
        upload_to='candidates/',
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.name} - {self.election.name}"


class Vote(models.Model):

    voter = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='votes'
    )

    election = models.ForeignKey(
        Election,
        on_delete=models.PROTECT,
        related_name='votes'
    )

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.PROTECT,
        related_name='votes'
    )

    voted_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['voter', 'election'],
                name='one_vote_per_voter_per_election'
            )
        ]

    def __str__(self):
        return f"{self.voter.username} - {self.election.name}"


class VoteOTP(models.Model):

    voter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vote_otps'
    )

    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name='vote_otps'
    )

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='vote_otps'
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
        return f"Vote OTP for {self.voter.username} - {self.election.name}"


class ElectionEligibleVoter(models.Model):

    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name='eligible_voters'
    )

    # This is the Aadhaar number entered/uploaded
    # by the admin for THIS election.
    aadhaar_number = models.CharField(
        max_length=5
    )

    added_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['election', 'aadhaar_number'],
                name='one_aadhaar_per_election'
            )
        ]

    def __str__(self):
        return f"{self.aadhaar_number} - {self.election.name}"