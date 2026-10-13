from django import forms

from election.models import (
    Election,
    Candidate
)


# =========================================================
# ELECTION FORM
# =========================================================

class ElectionForm(forms.ModelForm):

    eligible_voter_ids = forms.CharField(
        required=False,

        label='Eligible Aadhaar Numbers',

        widget=forms.Textarea(
            attrs={
                'placeholder': (
                    'Enter Aadhaar numbers separated '
                    'by commas or new lines.\n'
                    'Example:\n'
                    '12345\n'
                    '12346\n'
                    '12347'
                ),

                'rows': 6,
            }
        ),

        help_text=(
            'Enter 5-digit Aadhaar numbers. '
            'These voters will be eligible only '
            'for this election.'
        )
    )


    eligible_voters_file = forms.FileField(
        required=False,

        label='Upload Aadhaar Number CSV',

        help_text=(
            'CSV must contain a column named '
            'aadhaar_number.'
        )
    )


    class Meta:

        model = Election

        fields = [
            'name',
            'description',
            'start_date',
            'end_date',
            'eligibility_type',
        ]


        widgets = {

            'name': forms.TextInput(
                attrs={
                    'placeholder':
                        'Enter election name'
                }
            ),


            'description': forms.Textarea(
                attrs={
                    'placeholder':
                        'Enter election description',

                    'rows': 5,
                }
            ),


            'start_date': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',

                attrs={
                    'type':
                        'datetime-local'
                }
            ),


            'end_date': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',

                attrs={
                    'type':
                        'datetime-local'
                }
            ),


            'eligibility_type':
                forms.RadioSelect(),
        }


    input_formats = [
        '%Y-%m-%dT%H:%M'
    ]


# =========================================================
# CANDIDATE FORM
# =========================================================

class CandidateForm(forms.ModelForm):

    class Meta:

        model = Candidate

        fields = [
            'name',
            'party',
            'description',
            'photo'
        ]


        widgets = {

            'name': forms.TextInput(
                attrs={
                    'placeholder':
                        'Enter candidate name'
                }
            ),


            'party': forms.TextInput(
                attrs={
                    'placeholder':
                        'Enter party name'
                }
            ),


            'description': forms.Textarea(
                attrs={
                    'placeholder':
                        'Enter candidate description',

                    'rows': 5
                }
            ),


            'photo':
                forms.ClearableFileInput(),
        }