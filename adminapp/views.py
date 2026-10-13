import csv
import io

from django.contrib import messages
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)
from django.utils import timezone

from django.contrib.auth import (
    authenticate,
    login,
    logout
)

from django.contrib.auth.decorators import (
    login_required,
    user_passes_test
)

from django.db import transaction

from django.http import HttpResponse

from election.models import (
    Election,
    Candidate,
    Vote,
    ElectionEligibleVoter
)

from users.models import Voter

from .forms import (
    ElectionForm,
    CandidateForm
)


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(user):

    return (
        user.is_authenticated
        and user.is_staff
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

def admin_login(request):

    if request.method == 'POST':

        username = request.POST.get(
            'username'
        )

        password = request.POST.get(
            'password'
        )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None and user.is_staff:

            login(
                request,
                user
            )

            return redirect(
                'admin_dashboard'
            )

        return render(
            request,
            'adminapp/admin_login.html',
            {
                'error':
                    'Invalid admin username or password.'
            }
        )

    return render(
        request,
        'adminapp/admin_login.html'
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@login_required(login_url='admin_login')
def admin_dashboard(request):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    context = {

        'total_voters':
            Voter.objects.count(),

        'total_elections':
            Election.objects.count(),

        'total_candidates':
            Candidate.objects.count(),

        'total_votes':
            Vote.objects.count(),
    }

    return render(
        request,
        'adminapp/dashboard.html',
        context
    )


# =========================================================
# MANAGE ELECTIONS
# =========================================================

@login_required(login_url='admin_login')
def manage_elections(request):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    # -----------------------------------------------------
    # CLOSED ELECTIONS ARE NOT SHOWN HERE.
    #
    # They are kept in the database and shown on the
    # Election History page.
    # -----------------------------------------------------

    elections = (
        Election.objects
        .exclude(
            status='CLOSED'
        )
        .order_by(
            '-created_at'
        )
    )

    return render(
        request,
        'adminapp/manage_elections.html',
        {
            'elections':
                elections
        }
    )


# =========================================================
# CREATE ELECTION
# =========================================================

@user_passes_test(
    is_admin,
    login_url='admin_login'
)
def create_election(request):

    if request.method == 'POST':

        form = ElectionForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            eligibility_type = (
                form.cleaned_data[
                    'eligibility_type'
                ]
            )

            aadhaar_numbers = set()

            # =================================================
            # SELECTED AADHAAR MODE
            # =================================================

            if eligibility_type == 'SELECTED':

                manual_numbers = (
                    form.cleaned_data.get(
                        'eligible_voter_ids'
                    )
                )

                if manual_numbers:

                    manual_numbers = (
                        manual_numbers.replace(
                            ',',
                            '\n'
                        )
                    )

                    for value in (
                        manual_numbers.splitlines()
                    ):

                        value = value.strip()

                        if value:

                            aadhaar_numbers.add(
                                value
                            )

                # ---------------------------------------------
                # CSV FILE
                # ---------------------------------------------

                uploaded_file = (
                    form.cleaned_data.get(
                        'eligible_voters_file'
                    )
                )

                if uploaded_file:

                    if not uploaded_file.name.lower().endswith(
                        '.csv'
                    ):

                        form.add_error(
                            'eligible_voters_file',
                            'Please upload a CSV file.'
                        )

                        return render(
                            request,
                            'adminapp/create_election.html',
                            {
                                'form':
                                    form
                            }
                        )

                    try:

                        content = (
                            uploaded_file.read()
                            .decode(
                                'utf-8-sig'
                            )
                        )

                        reader = csv.DictReader(
                            io.StringIO(
                                content
                            )
                        )

                        if not reader.fieldnames:

                            form.add_error(
                                'eligible_voters_file',
                                'The CSV file is empty.'
                            )

                            return render(
                                request,
                                'adminapp/create_election.html',
                                {
                                    'form':
                                        form
                                }
                            )

                        reader.fieldnames = [

                            field.strip()
                            if field
                            else field

                            for field
                            in reader.fieldnames

                        ]

                        if (
                            'aadhaar_number'
                            not in reader.fieldnames
                        ):

                            form.add_error(
                                'eligible_voters_file',
                                (
                                    'CSV must contain '
                                    'an aadhaar_number column.'
                                )
                            )

                            return render(
                                request,
                                'adminapp/create_election.html',
                                {
                                    'form':
                                        form
                                }
                            )

                        for row in reader:

                            aadhaar = row.get(
                                'aadhaar_number'
                            )

                            if aadhaar:

                                aadhaar = (
                                    aadhaar.strip()
                                )

                                if aadhaar:

                                    aadhaar_numbers.add(
                                        aadhaar
                                    )

                    except UnicodeDecodeError:

                        form.add_error(
                            'eligible_voters_file',
                            (
                                'CSV must use '
                                'UTF-8 encoding.'
                            )
                        )

                        return render(
                            request,
                            'adminapp/create_election.html',
                            {
                                'form':
                                    form
                            }
                        )

                # ---------------------------------------------
                # CHECK AT LEAST ONE AADHAAR
                # ---------------------------------------------

                if not aadhaar_numbers:

                    form.add_error(
                        'eligible_voter_ids',
                        (
                            'Enter or upload at least '
                            'one Aadhaar number.'
                        )
                    )

                    return render(
                        request,
                        'adminapp/create_election.html',
                        {
                            'form':
                                form
                        }
                    )

                # ---------------------------------------------
                # VALIDATE 5 DIGITS
                # ---------------------------------------------

                invalid_numbers = [

                    aadhaar

                    for aadhaar
                    in aadhaar_numbers

                    if (
                        not aadhaar.isdigit()
                        or len(aadhaar) != 5
                    )

                ]

                if invalid_numbers:

                    form.add_error(
                        'eligible_voter_ids',
                        (
                            'Invalid Aadhaar numbers: '
                            + ', '.join(
                                sorted(
                                    invalid_numbers
                                )
                            )
                            + '. Each Aadhaar number '
                              'must contain exactly 5 digits.'
                        )
                    )

                    return render(
                        request,
                        'adminapp/create_election.html',
                        {
                            'form':
                                form
                        }
                    )

            # =================================================
            # CREATE ELECTION
            # =================================================

            with transaction.atomic():

                election = form.save(
                    commit=False
                )

                # New elections always begin as DRAFT.
                election.status = 'DRAFT'

                election.save()

                # ---------------------------------------------
                # SAVE SELECTED AADHAAR NUMBERS
                # ---------------------------------------------

                if eligibility_type == 'SELECTED':

                    ElectionEligibleVoter.objects.bulk_create(

                        [
                            ElectionEligibleVoter(
                                election=election,
                                aadhaar_number=aadhaar
                            )

                            for aadhaar
                            in sorted(
                                aadhaar_numbers
                            )
                        ]

                    )

            messages.success(
                request,
                'Election created successfully.'
            )

            return redirect(
                'manage_elections'
            )

    else:

        form = ElectionForm()

    return render(
        request,
        'adminapp/create_election.html',
        {
            'form':
                form
        }
    )


# =========================================================
# EDIT ELECTION
# =========================================================

@user_passes_test(
    is_admin,
    login_url='admin_login'
)
def edit_election(
    request,
    election_id
):

    election = get_object_or_404(
        Election,
        id=election_id
    )

    original_status = (
        election.status
    )

    existing_aadhaar_numbers = list(

        ElectionEligibleVoter.objects
        .filter(
            election=election
        )
        .order_by(
            'aadhaar_number'
        )
        .values_list(
            'aadhaar_number',
            flat=True
        )

    )

    existing_aadhaar_text = (
        '\n'.join(
            existing_aadhaar_numbers
        )
    )

    # =====================================================
    # POST
    # =====================================================

    if request.method == 'POST':

        form = ElectionForm(
            request.POST,
            request.FILES,
            instance=election
        )

        if form.is_valid():

            eligibility_type = (
                form.cleaned_data[
                    'eligibility_type'
                ]
            )

            aadhaar_numbers = set()

            # =================================================
            # SELECTED MODE
            # =================================================

            if eligibility_type == 'SELECTED':

                manual_numbers = (
                    form.cleaned_data.get(
                        'eligible_voter_ids'
                    )
                )

                if manual_numbers:

                    manual_numbers = (
                        manual_numbers.replace(
                            ',',
                            '\n'
                        )
                    )

                    for value in (
                        manual_numbers.splitlines()
                    ):

                        value = value.strip()

                        if value:

                            aadhaar_numbers.add(
                                value
                            )

                # ---------------------------------------------
                # CSV UPLOAD
                # ---------------------------------------------

                uploaded_file = (
                    form.cleaned_data.get(
                        'eligible_voters_file'
                    )
                )

                if uploaded_file:

                    if not uploaded_file.name.lower().endswith(
                        '.csv'
                    ):

                        form.add_error(
                            'eligible_voters_file',
                            'Please upload a CSV file.'
                        )

                        return render(
                            request,
                            'adminapp/edit_election.html',
                            {
                                'form':
                                    form,

                                'election':
                                    election,

                                'existing_aadhaar_text':
                                    existing_aadhaar_text,

                                'candidates':
                                    Candidate.objects.filter(
                                        election=election
                                    ).order_by(
                                        'name'
                                    ),

                                'eligible_count':
                                    len(
                                        existing_aadhaar_numbers
                                    )
                            }
                        )

                    try:

                        content = (
                            uploaded_file.read()
                            .decode(
                                'utf-8-sig'
                            )
                        )

                        reader = csv.DictReader(
                            io.StringIO(
                                content
                            )
                        )

                        if not reader.fieldnames:

                            form.add_error(
                                'eligible_voters_file',
                                'The CSV file is empty.'
                            )

                            return render(
                                request,
                                'adminapp/edit_election.html',
                                {
                                    'form':
                                        form,

                                    'election':
                                        election,

                                    'existing_aadhaar_text':
                                        existing_aadhaar_text,

                                    'candidates':
                                        Candidate.objects.filter(
                                            election=election
                                        ).order_by(
                                            'name'
                                        ),

                                    'eligible_count':
                                        len(
                                            existing_aadhaar_numbers
                                        )
                                }
                            )

                        reader.fieldnames = [

                            field.strip()
                            if field
                            else field

                            for field
                            in reader.fieldnames

                        ]

                        if (
                            'aadhaar_number'
                            not in reader.fieldnames
                        ):

                            form.add_error(
                                'eligible_voters_file',
                                (
                                    'CSV must contain '
                                    'an aadhaar_number column.'
                                )
                            )

                            return render(
                                request,
                                'adminapp/edit_election.html',
                                {
                                    'form':
                                        form,

                                    'election':
                                        election,

                                    'existing_aadhaar_text':
                                        existing_aadhaar_text,

                                    'candidates':
                                        Candidate.objects.filter(
                                            election=election
                                        ).order_by(
                                            'name'
                                        ),

                                    'eligible_count':
                                        len(
                                            existing_aadhaar_numbers
                                        )
                                }
                            )

                        for row in reader:

                            aadhaar = row.get(
                                'aadhaar_number'
                            )

                            if aadhaar:

                                aadhaar = (
                                    aadhaar.strip()
                                )

                                if aadhaar:

                                    aadhaar_numbers.add(
                                        aadhaar
                                    )

                    except UnicodeDecodeError:

                        form.add_error(
                            'eligible_voters_file',
                            'CSV must use UTF-8 encoding.'
                        )

                        return render(
                            request,
                            'adminapp/edit_election.html',
                            {
                                'form':
                                    form,

                                'election':
                                    election,

                                'existing_aadhaar_text':
                                    existing_aadhaar_text,

                                'candidates':
                                    Candidate.objects.filter(
                                        election=election
                                    ).order_by(
                                        'name'
                                    ),

                                'eligible_count':
                                    len(
                                        existing_aadhaar_numbers
                                    )
                            }
                        )

                # ---------------------------------------------
                # MUST HAVE AT LEAST ONE
                # ---------------------------------------------

                if not aadhaar_numbers:

                    form.add_error(
                        'eligible_voter_ids',
                        (
                            'Enter or upload at least '
                            'one Aadhaar number.'
                        )
                    )

                    return render(
                        request,
                        'adminapp/edit_election.html',
                        {
                            'form':
                                form,

                            'election':
                                election,

                            'existing_aadhaar_text':
                                existing_aadhaar_text,

                            'candidates':
                                Candidate.objects.filter(
                                    election=election
                                ).order_by(
                                    'name'
                                ),

                            'eligible_count':
                                len(
                                    existing_aadhaar_numbers
                                )
                        }
                    )

                # ---------------------------------------------
                # VALIDATE 5 DIGITS
                # ---------------------------------------------

                invalid_numbers = [

                    aadhaar

                    for aadhaar
                    in aadhaar_numbers

                    if (
                        not aadhaar.isdigit()
                        or len(aadhaar) != 5
                    )

                ]

                if invalid_numbers:

                    form.add_error(
                        'eligible_voter_ids',
                        (
                            'Invalid Aadhaar numbers: '
                            + ', '.join(
                                sorted(
                                    invalid_numbers
                                )
                            )
                            + '. Each Aadhaar number '
                              'must contain exactly 5 digits.'
                        )
                    )

                    return render(
                        request,
                        'adminapp/edit_election.html',
                        {
                            'form':
                                form,

                            'election':
                                election,

                            'existing_aadhaar_text':
                                existing_aadhaar_text,

                            'candidates':
                                Candidate.objects.filter(
                                    election=election
                                ).order_by(
                                    'name'
                                ),

                            'eligible_count':
                                len(
                                    existing_aadhaar_numbers
                                )
                        }
                    )

            # =================================================
            # SAVE ELECTION
            # =================================================

            with transaction.atomic():

                election = form.save(
                    commit=False
                )

                # Preserve existing status.
                election.status = (
                    original_status
                )

                election.save()

                # ---------------------------------------------
                # REPLACE ELIGIBILITY LIST
                # ---------------------------------------------

                ElectionEligibleVoter.objects.filter(
                    election=election
                ).delete()

                if eligibility_type == 'SELECTED':

                    ElectionEligibleVoter.objects.bulk_create(

                        [
                            ElectionEligibleVoter(
                                election=election,
                                aadhaar_number=aadhaar
                            )

                            for aadhaar
                            in sorted(
                                aadhaar_numbers
                            )
                        ]

                    )

            messages.success(
                request,
                (
                    'Election and voter eligibility '
                    'updated successfully.'
                )
            )

            return redirect(
                'manage_elections'
            )

    else:

        form = ElectionForm(
            instance=election,

            initial={
                'eligible_voter_ids':
                    existing_aadhaar_text
            }
        )

    # =====================================================
    # CANDIDATES
    # =====================================================

    candidates = (

        Candidate.objects
        .filter(
            election=election
        )
        .order_by(
            'name'
        )

    )

    # =====================================================
    # ELIGIBLE COUNT
    # =====================================================

    eligible_count = (

        ElectionEligibleVoter.objects
        .filter(
            election=election
        )
        .count()

    )

    return render(
        request,
        'adminapp/edit_election.html',
        {
            'form':
                form,

            'election':
                election,

            'existing_aadhaar_text':
                existing_aadhaar_text,

            'candidates':
                candidates,

            'eligible_count':
                eligible_count,
        }
    )


# =========================================================
# DOWNLOAD ELECTION ELIGIBILITY CSV
# =========================================================

@user_passes_test(
    is_admin,
    login_url='admin_login'
)
def download_eligibility_csv(
    request,
    election_id
):

    election = get_object_or_404(
        Election,
        id=election_id
    )

    response = HttpResponse(
        content_type='text/csv'
    )

    filename = (
        f'{election.name}_eligibility.csv'
        .replace(
            ' ',
            '_'
        )
    )

    response[
        'Content-Disposition'
    ] = (
        f'attachment; filename="{filename}"'
    )

    writer = csv.writer(
        response
    )

    writer.writerow([
        'aadhaar_number'
    ])

    # -----------------------------------------------------
    # SELECTED MODE
    # -----------------------------------------------------

    if election.eligibility_type == 'SELECTED':

        aadhaar_numbers = (

            ElectionEligibleVoter.objects
            .filter(
                election=election
            )
            .order_by(
                'aadhaar_number'
            )
            .values_list(
                'aadhaar_number',
                flat=True
            )

        )

        for aadhaar in aadhaar_numbers:

            writer.writerow([
                aadhaar
            ])

    # -----------------------------------------------------
    # EVERYONE MODE
    # -----------------------------------------------------

    else:

        aadhaar_numbers = (

            Voter.objects
            .filter(
                is_active=True
            )
            .order_by(
                'aadhaar_number'
            )
            .values_list(
                'aadhaar_number',
                flat=True
            )

        )

        for aadhaar in aadhaar_numbers:

            writer.writerow([
                aadhaar
            ])

    return response


# =========================================================
# ARCHIVE / REMOVE ELECTION FROM MANAGE ELECTIONS
# =========================================================

@login_required(login_url='admin_login')
def delete_election(
    request,
    election_id
):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    election = get_object_or_404(
        Election,
        id=election_id
    )

    # -----------------------------------------------------
    # ONLY POST IS ALLOWED
    # -----------------------------------------------------

    if request.method != 'POST':

        return redirect(
            'manage_elections'
        )

    # -----------------------------------------------------
    # ALREADY CLOSED
    # -----------------------------------------------------

    if election.status == 'CLOSED':

        messages.info(
            request,
            (
                f'"{election.name}" is already '
                'in Election History.'
            )
        )

        return redirect(
            'manage_elections'
        )

    # -----------------------------------------------------
    # ARCHIVE ELECTION
    #
    # IMPORTANT:
    #
    # We DO NOT call:
    #
    #     election.delete()
    #
    # Therefore:
    #
    #     Election
    #     Candidates
    #     Votes
    #     Vote OTP records
    #     Eligibility records
    #     Results
    #
    # are preserved.
    # -----------------------------------------------------

    election.status = 'CLOSED'

    election.save(
        update_fields=[
            'status'
        ]
    )

    messages.success(
        request,
        (
            f'"{election.name}" has been moved '
            'to Election History.'
        )
    )

    return redirect(
        'manage_elections'
    )


# =========================================================
# ELECTION HISTORY
# =========================================================

@login_required(login_url='admin_login')
def election_history(request):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    elections = (
        Election.objects
        .filter(
            status='CLOSED'
        )
        .prefetch_related(
            'candidates',
            'votes',
            'eligible_voters'
        )
        .order_by(
            '-end_date'
        )
    )

    return render(
        request,
        'adminapp/election_history.html',
        {
            'elections':
                elections
        }
    )


# =========================================================
# START ELECTION
# =========================================================

@user_passes_test(
    is_admin,
    login_url='admin_login'
)
def start_election(
    request,
    election_id
):

    election = get_object_or_404(
        Election,
        id=election_id
    )

    # -----------------------------------------------------
    # CHECK STATUS
    # -----------------------------------------------------

    if election.status == 'ONGOING':

        messages.error(
            request,
            'This election is already ongoing.'
        )

        return redirect(
            'manage_elections'
        )

    if election.status == 'CLOSED':

        messages.error(
            request,
            'A closed election cannot be started again.'
        )

        return redirect(
            'manage_elections'
        )

    # -----------------------------------------------------
    # CHECK CANDIDATES
    # -----------------------------------------------------

    candidate_count = (

        Candidate.objects
        .filter(
            election=election
        )
        .count()

    )

    if candidate_count == 0:

        messages.error(
            request,
            (
                'Cannot start the election. '
                'Please add at least one candidate first.'
            )
        )

        return redirect(
            'manage_elections'
        )

    # =====================================================
    # TIMEZONE-SAFE TIME CHECK
    # =====================================================

    current_time = timezone.localtime(
        timezone.now()
    )

    start_time = timezone.localtime(
        election.start_date
    )

    end_time = timezone.localtime(
        election.end_date
    )

    # -----------------------------------------------------
    # CHECK START TIME
    # -----------------------------------------------------

    if current_time < start_time:

        messages.error(
            request,
            (
                'The election has not reached '
                'its start time yet.\n\n'

                f'Start time: '
                f'{start_time.strftime("%d %b %Y, %I:%M %p")}\n'

                f'Current time: '
                f'{current_time.strftime("%d %b %Y, %I:%M %p")}'
            )
        )

        return redirect(
            'manage_elections'
        )

    # -----------------------------------------------------
    # CHECK END TIME
    # -----------------------------------------------------

    if current_time >= end_time:

        messages.error(
            request,
            (
                'The election end time has already passed.\n\n'

                f'End time: '
                f'{end_time.strftime("%d %b %Y, %I:%M %p")}'
            )
        )

        return redirect(
            'manage_elections'
        )

    # =====================================================
    # START ELECTION
    # =====================================================

    election.status = 'ONGOING'

    election.save(
        update_fields=[
            'status'
        ]
    )

    messages.success(
        request,
        (
            f'Election "{election.name}" '
            'started successfully.'
        )
    )

    return redirect(
        'manage_elections'
    )


# =========================================================
# CLOSE ELECTION
# =========================================================

@login_required(login_url='admin_login')
def close_election(
    request,
    election_id
):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    election = get_object_or_404(
        Election,
        id=election_id
    )

    if request.method == 'POST':

        election.status = 'CLOSED'

        election.save(
            update_fields=[
                'status'
            ]
        )

        messages.success(
            request,
            (
                f'Election "{election.name}" '
                'has been closed.'
            )
        )

    return redirect(
        'manage_elections'
    )


# =========================================================
# CANDIDATE MANAGEMENT
# =========================================================

@login_required(login_url='admin_login')
def manage_candidates(request):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    show_old = (
        request.GET.get('show')
        == 'old'
    )

    if show_old:

        candidates = (

            Candidate.objects
            .filter(
                election__status='CLOSED'
            )
            .select_related(
                'election'
            )
            .order_by(
                '-election__end_date',
                'name'
            )

        )

    else:

        candidates = (

            Candidate.objects
            .exclude(
                election__status='CLOSED'
            )
            .select_related(
                'election'
            )
            .order_by(
                'election__name',
                'name'
            )

        )

    return render(
        request,
        'adminapp/manage_candidates.html',
        {
            'candidates':
                candidates,

            'show_old':
                show_old
        }
    )


# =========================================================
# CREATE CANDIDATE
# =========================================================

@login_required(login_url='admin_login')
def create_candidate(request):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    elections = (

        Election.objects
        .exclude(
            status='CLOSED'
        )
        .order_by(
            'name'
        )

    )

    if request.method == 'POST':

        election_id = request.POST.get(
            'election'
        )

        election = get_object_or_404(
            Election,
            id=election_id
        )

        if election.status == 'CLOSED':

            messages.error(
                request,
                (
                    'Candidates cannot be added '
                    'to a closed election.'
                )
            )

            return redirect(
                'manage_candidates'
            )

        form = CandidateForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            candidate = form.save(
                commit=False
            )

            candidate.election = election

            candidate.save()

            messages.success(
                request,
                (
                    f'Candidate "{candidate.name}" '
                    'added successfully.'
                )
            )

            return redirect(
                'manage_candidates'
            )

    else:

        form = CandidateForm()

    return render(
        request,
        'adminapp/create_candidate.html',
        {
            'form':
                form,

            'elections':
                elections
        }
    )


# =========================================================
# EDIT CANDIDATE
# =========================================================

@login_required(login_url='admin_login')
def edit_candidate(
    request,
    candidate_id
):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    candidate = get_object_or_404(
        Candidate,
        id=candidate_id
    )

    elections = (

        Election.objects
        .exclude(
            status='CLOSED'
        )
        .order_by(
            'name'
        )

    )

    if request.method == 'POST':

        election_id = request.POST.get(
            'election'
        )

        election = get_object_or_404(
            Election,
            id=election_id
        )

        if election.status == 'CLOSED':

            messages.error(
                request,
                (
                    'Candidates cannot be moved '
                    'to a closed election.'
                )
            )

            return redirect(
                'manage_candidates'
            )

        form = CandidateForm(
            request.POST,
            request.FILES,
            instance=candidate
        )

        if form.is_valid():

            candidate = form.save(
                commit=False
            )

            candidate.election = election

            candidate.save()

            messages.success(
                request,
                'Candidate updated successfully.'
            )

            return redirect(
                'manage_candidates'
            )

    else:

        form = CandidateForm(
            instance=candidate
        )

    return render(
        request,
        'adminapp/create_candidate.html',
        {
            'form':
                form,

            'elections':
                elections,

            'edit_mode':
                True,

            'candidate':
                candidate
        }
    )


# =========================================================
# DELETE CANDIDATE
# =========================================================

@login_required(login_url='admin_login')
def delete_candidate(
    request,
    candidate_id
):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    candidate = get_object_or_404(
        Candidate,
        id=candidate_id
    )

    if request.method == 'POST':

        candidate_name = candidate.name

        candidate.delete()

        messages.success(
            request,
            (
                f'Candidate "{candidate_name}" '
                'deleted successfully.'
            )
        )

        return redirect(
            'manage_candidates'
        )

    return render(
        request,
        'adminapp/delete_candidate.html',
        {
            'candidate':
                candidate
        }
    )


# =========================================================
# VIEW RESULTS
# =========================================================

@login_required(login_url='admin_login')
def view_results(request):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    elections = (

        Election.objects
        .all()
        .order_by(
            '-created_at'
        )

    )

    selected_election = None

    results = []

    election_id = request.GET.get(
        'election'
    )

    if election_id:

        selected_election = get_object_or_404(
            Election,
            id=election_id
        )

        candidates = (

            Candidate.objects
            .filter(
                election=selected_election
            )
            .order_by(
                'name'
            )

        )

        for candidate in candidates:

            vote_count = (

                Vote.objects
                .filter(
                    election=selected_election,
                    candidate=candidate
                )
                .count()

            )

            results.append(
                {
                    'candidate':
                        candidate,

                    'vote_count':
                        vote_count
                }
            )

    return render(
        request,
        'adminapp/results.html',
        {
            'elections':
                elections,

            'selected_election':
                selected_election,

            'results':
                results,
        }
    )


# =========================================================
# PUBLISH RESULTS
# =========================================================

@login_required(login_url='admin_login')
def publish_results(
    request,
    election_id
):

    if not request.user.is_staff:

        messages.error(
            request,
            'You are not authorized to access this page.'
        )

        return redirect(
            'admin_login'
        )

    election = get_object_or_404(
        Election,
        id=election_id
    )

    if request.method == 'POST':

        if election.status != 'CLOSED':

            messages.error(
                request,
                (
                    'Results can only be published '
                    'after the election is closed.'
                )
            )

            return redirect(
                'view_results'
            )

        election.results_published = True

        election.save(
            update_fields=[
                'results_published'
            ]
        )

        messages.success(
            request,
            (
                f'Results for "{election.name}" '
                'have been published.'
            )
        )

    return redirect(
        f'/admin-panel/results/?election={election.id}'
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

def admin_logout(request):

    logout(
        request
    )

    return redirect(
        'admin_login'
    )