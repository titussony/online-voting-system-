from django import forms
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

from .models import Voter


class VoterRegistrationForm(forms.ModelForm):

    username = forms.CharField(
        max_length=150
    )

    email = forms.EmailField()

    password = forms.CharField(
        widget=forms.PasswordInput
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput
    )

    class Meta:

        model = Voter

        fields = [
            'username',
            'email',
            'password',
            'confirm_password',
            'full_name',
            'phone',
            'aadhaar_number',
            'voter_id',
            'date_of_birth',
            'address',
        ]

        widgets = {
            'date_of_birth': forms.DateInput(
                attrs={'type': 'date'}
            ),

            'address': forms.Textarea(
                attrs={'rows': 4}
            ),
        }

    # ==========================================
    # AADHAAR VALIDATION
    # ==========================================

    def clean_aadhaar_number(self):

        aadhaar_number = self.cleaned_data.get(
            'aadhaar_number'
        )

        if not aadhaar_number:
            return aadhaar_number

        if not aadhaar_number.isdigit():
            raise forms.ValidationError(
                'Aadhaar number must contain only digits.'
            )

        if len(aadhaar_number) != 5:
            raise forms.ValidationError(
                'Aadhaar number must contain exactly 5 digits.'
            )

        return aadhaar_number

    # ==========================================
    # USERNAME VALIDATION
    # ==========================================

    def clean_username(self):

        username = self.cleaned_data['username']

        if User.objects.filter(
            username=username
        ).exists():

            raise forms.ValidationError(
                'This username is already taken.'
            )

        return username

    # ==========================================
    # EMAIL VALIDATION
    # ==========================================

    def clean_email(self):

        email = self.cleaned_data['email']

        if User.objects.filter(
            email=email
        ).exists():

            raise forms.ValidationError(
                'An account with this email already exists.'
            )

        return email

    # ==========================================
    # PASSWORD VALIDATION
    # ==========================================

    def clean(self):

        cleaned_data = super().clean()

        password = cleaned_data.get(
            'password'
        )

        confirm_password = cleaned_data.get(
            'confirm_password'
        )

        if password and confirm_password:

            if password != confirm_password:

                raise forms.ValidationError(
                    'Passwords do not match.'
                )

        return cleaned_data