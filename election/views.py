import random
import os

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import (
    render,
    get_object_or_404,
    redirect
)
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.colors import HexColor

from .models import (
    Election,
    Candidate,
    Vote,
    VoteOTP,
    ElectionEligibleVoter,
)


# =========================================================
# ELECTION ELIGIBILITY HELPER
# =========================================================

def election_allows_voter(election, aadhaar_number):
    """
    Check whether the Aadhaar number is allowed to vote
    in this particular election.

    EVERYONE:
        Any properly verified registered account can vote.

    SELECTED:
        The Aadhaar number must be present in the
        election-specific eligibility list.
    """

    if election.eligibility_type == 'EVERYONE':
        return True

    return ElectionEligibleVoter.objects.filter(
        election=election,
        aadhaar_number=aadhaar_number
    ).exists()


# =========================================================
# ELECTION LIST
# =========================================================

@login_required(login_url='voter_login')
def election_list(request):

    now = timezone.now()

    elections = Election.objects.filter(
        status='ONGOING',
        start_date__lte=now,
        end_date__gte=now
    ).order_by('end_date')

    return render(
        request,
        'election/election_list.html',
        {
            'elections': elections
        }
    )


# =========================================================
# ELECTION DETAIL / VOTING
# =========================================================

@login_required(login_url='voter_login')
def election_detail(request, election_id):

    now = timezone.now()

    election = get_object_or_404(
        Election,
        id=election_id,
        status='ONGOING',
        start_date__lte=now,
        end_date__gte=now
    )

    candidates = election.candidates.all().order_by('name')

    # -----------------------------------------------------
    # CHECK VOTER PROFILE
    # -----------------------------------------------------

    voter = getattr(
        request.user,
        'voter_profile',
        None
    )

    if voter is None:

        messages.error(
            request,
            'Voter profile not found.'
        )

        return redirect('voter_dashboard')

    # -----------------------------------------------------
    # CHECK WHETHER USER ALREADY VOTED
    # -----------------------------------------------------

    existing_vote = (
        Vote.objects
        .select_related(
            'election',
            'candidate'
        )
        .filter(
            voter=request.user,
            election=election
        )
        .first()
    )

    has_voted = existing_vote is not None

    # -----------------------------------------------------
    # VOTE FORM SUBMISSION
    # -----------------------------------------------------

    if request.method == 'POST':

        # =================================================
        # BASIC ACCOUNT VERIFICATION
        # =================================================

        if not voter.email_verified:

            messages.error(
                request,
                'Please verify your email before voting.'
            )

            return redirect('verify_email')

        if not voter.face_verified:

            messages.error(
                request,
                'Please complete face verification before voting.'
            )

            return redirect('face_verification')

        if not voter.is_verified:

            messages.error(
                request,
                'Your voter account is not verified.'
            )

            return redirect('voter_dashboard')

        if not voter.is_active:

            messages.error(
                request,
                'Your voter account is inactive.'
            )

            return redirect('voter_dashboard')

        # =================================================
        # CHECK IF ALREADY VOTED
        # =================================================

        if has_voted:

            messages.error(
                request,
                'You have already voted in this election.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        # =================================================
        # GET AADHAAR
        # =================================================

        entered_aadhaar = request.POST.get(
            'aadhaar_number',
            ''
        ).strip()

        # =================================================
        # AADHAAR FORMAT CHECK
        # =================================================

        if not entered_aadhaar:

            messages.error(
                request,
                'Please enter your Aadhaar number.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        if (
            not entered_aadhaar.isdigit()
            or len(entered_aadhaar) != 5
        ):

            messages.error(
                request,
                'Aadhaar number must contain exactly 5 digits.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        # =================================================
        # AADHAAR MUST MATCH LOGGED-IN ACCOUNT
        # =================================================

        if entered_aadhaar != voter.aadhaar_number:

            messages.error(
                request,
                'The Aadhaar number does not match your account.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        # =================================================
        # ELECTION-SPECIFIC ELIGIBILITY
        # =================================================

        if not election_allows_voter(
            election,
            entered_aadhaar
        ):

            messages.error(
                request,
                'You are not eligible to vote in this election.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        # =================================================
        # GET SELECTED CANDIDATE
        # =================================================

        candidate_id = request.POST.get(
            'candidate'
        )

        if not candidate_id:

            messages.error(
                request,
                'Please select a candidate.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        # =================================================
        # CANDIDATE MUST BELONG TO THIS ELECTION
        # =================================================

        candidate = get_object_or_404(
            Candidate,
            id=candidate_id,
            election=election
        )

        # =================================================
        # STORE VOTING INFORMATION IN SESSION
        # =================================================

        request.session['vote_candidate_id'] = candidate.id

        request.session['vote_election_id'] = election.id

        request.session['vote_aadhaar'] = entered_aadhaar

        request.session['vote_aadhaar_verified'] = True

        # =================================================
        # GO TO FACE VERIFICATION
        # =================================================

        return redirect(
            'vote_face_verification',
            election_id=election.id
        )

    # =====================================================
    # DISPLAY ELECTION PAGE
    # =====================================================

    return render(
        request,
        'election/election_detail.html',
        {
            'election': election,
            'candidates': candidates,
            'has_voted': has_voted,
            'existing_vote': existing_vote,
        }
    )


# =========================================================
# VOTING FACE VERIFICATION
# =========================================================

@login_required(login_url='voter_login')
def vote_face_verification(request, election_id):

    # Import existing face comparison function
    from users.views import compare_faces

    # -----------------------------------------------------
    # GET VOTER PROFILE
    # -----------------------------------------------------

    voter = getattr(
        request.user,
        'voter_profile',
        None
    )

    if voter is None:

        return JsonResponse({
            'success': False,
            'message': 'Voter profile not found.'
        })

    # -----------------------------------------------------
    # GET ELECTION
    # -----------------------------------------------------

    election = get_object_or_404(
        Election,
        id=election_id,
        status='ONGOING'
    )

    # =====================================================
    # MAKE SURE ELECTION IS STILL OPEN
    # =====================================================

    now = timezone.now()

    if not (
        election.start_date <= now
        and election.end_date >= now
    ):

        messages.error(
            request,
            'This election is no longer open for voting.'
        )

        return redirect('election_list')

    # =====================================================
    # BASIC ACCOUNT VERIFICATION
    # =====================================================

    if not voter.email_verified:

        messages.error(
            request,
            'Please verify your email before voting.'
        )

        return redirect('verify_email')

    if not voter.face_verified:

        messages.error(
            request,
            'Please complete face verification before voting.'
        )

        return redirect('face_verification')

    if not voter.is_verified:

        messages.error(
            request,
            'Your voter account is not verified.'
        )

        return redirect('voter_dashboard')

    if not voter.is_active:

        messages.error(
            request,
            'Your voter account is inactive.'
        )

        return redirect('voter_dashboard')

    # =====================================================
    # AADHAAR VERIFICATION
    # =====================================================

    session_aadhaar = request.session.get(
        'vote_aadhaar'
    )

    aadhaar_verified = request.session.get(
        'vote_aadhaar_verified',
        False
    )

    if not aadhaar_verified or not session_aadhaar:

        messages.error(
            request,
            'Please verify your Aadhaar number before voting.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # -----------------------------------------------------
    # SESSION AADHAAR MUST MATCH ACCOUNT
    # -----------------------------------------------------

    if session_aadhaar != voter.aadhaar_number:

        request.session.pop(
            'vote_aadhaar',
            None
        )

        request.session.pop(
            'vote_aadhaar_verified',
            None
        )

        messages.error(
            request,
            'Aadhaar verification failed.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # =====================================================
    # CHECK ELECTION-SPECIFIC ELIGIBILITY
    # =====================================================

    if not election_allows_voter(
        election,
        session_aadhaar
    ):

        messages.error(
            request,
            'You are not eligible to vote in this election.'
        )

        return redirect(
            'election_list'
        )

    # =====================================================
    # CHECK IF ALREADY VOTED
    # =====================================================

    if Vote.objects.filter(
        voter=request.user,
        election=election
    ).exists():

        messages.error(
            request,
            'You have already voted in this election.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # =====================================================
    # GET CANDIDATE FROM SESSION
    # =====================================================

    candidate_id = request.session.get(
        'vote_candidate_id'
    )

    session_election_id = request.session.get(
        'vote_election_id'
    )

    if (
        not candidate_id
        or session_election_id != election.id
    ):

        messages.error(
            request,
            'Voting session expired. Please select a candidate again.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    candidate = get_object_or_404(
        Candidate,
        id=candidate_id,
        election=election
    )

    # =====================================================
    # GET REQUEST
    # =====================================================

    if request.method == 'GET':

        return render(
            request,
            'election/vote_face_verification.html',
            {
                'election': election,
                'candidate': candidate,
            }
        )

    # =====================================================
    # POST REQUEST
    # =====================================================

    live_photo = request.FILES.get(
        'live_photo'
    )

    if live_photo is None:

        return JsonResponse({
            'success': False,
            'message': 'No camera image received.'
        })

    # =====================================================
    # CREATE TEMPORARY DIRECTORY
    # =====================================================

    temp_directory = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        ),
        'media',
        'face_temp'
    )

    os.makedirs(
        temp_directory,
        exist_ok=True
    )

    temp_path = os.path.join(
        temp_directory,
        f'{request.user.id}_vote_live.jpg'
    )

    try:

        # =================================================
        # SAVE LIVE CAMERA IMAGE
        # =================================================

        with open(
            temp_path,
            'wb'
        ) as destination:

            for chunk in live_photo.chunks():

                destination.write(chunk)

        # =================================================
        # REGISTERED FACE PHOTO
        # =================================================

        registration_photo = voter.photo.path

        # =================================================
        # COMPARE FACES
        # =================================================

        verified, score = compare_faces(
            registration_photo,
            temp_path
        )

        print(
            f'Voting face similarity score: {score:.4f}'
        )

        # =================================================
        # FACE DOES NOT MATCH
        # =================================================

        if not verified:

            return JsonResponse({
                'success': False,
                'message':
                    'Face does not match the registered photo. '
                    'Please try again.'
            })

        # =================================================
        # FACE MATCHED
        # =================================================

        VoteOTP.objects.filter(
            voter=request.user,
            election=election,
            is_used=False
        ).update(
            is_used=True
        )

        # =================================================
        # GENERATE 6-DIGIT OTP
        # =================================================

        otp = str(
            random.randint(
                100000,
                999999
            )
        )

        # =================================================
        # SAVE VOTING OTP
        # =================================================

        VoteOTP.objects.create(
            voter=request.user,
            election=election,
            candidate=candidate,
            otp=otp
        )

        # =================================================
        # SEND OTP TO EMAIL
        # =================================================

        try:

            send_mail(
                subject='ProjectVote Voting OTP',

                message=(
                    f'Your ProjectVote voting OTP is: {otp}\n\n'
                    'This OTP is valid for 5 minutes.\n\n'
                    f'Election: {election.name}\n'
                    f'Candidate selected: {candidate.name}\n\n'
                    'Do not share this OTP with anyone.'
                ),

                from_email=None,

                recipient_list=[
                    request.user.email
                ],

                fail_silently=False
            )

        except Exception as error:

            print(
                'Voting OTP email error:',
                error
            )

            VoteOTP.objects.filter(
                voter=request.user,
                election=election,
                otp=otp,
                is_used=False
            ).update(
                is_used=True
            )

            return JsonResponse({
                'success': False,
                'message':
                    'Unable to send voting OTP. Please try again.'
            })

        # =================================================
        # SUCCESS
        # =================================================

        return JsonResponse({
            'success': True,
            'message':
                'Face verified successfully. '
                'Voting OTP has been sent to your email.',
            'redirect_url':
                f'/elections/{election.id}/verify-vote-otp/'
        })

    # =====================================================
    # GENERAL ERROR
    # =====================================================

    except Exception as error:

        print(
            '================================='
        )

        print(
            'VOTING FACE VERIFICATION ERROR'
        )

        print(
            type(error).__name__
        )

        print(
            str(error)
        )

        print(
            '================================='
        )

        return JsonResponse({
            'success': False,
            'message':
                'Face verification failed. '
                'Please try again.'
        })

    # =====================================================
    # DELETE TEMPORARY IMAGE
    # =====================================================

    finally:

        if os.path.exists(temp_path):

            os.remove(temp_path)


# =========================================================
# VERIFY VOTING OTP
# =========================================================

@login_required(login_url='voter_login')
def verify_vote_otp(request, election_id):

    # -----------------------------------------------------
    # GET ELECTION
    # -----------------------------------------------------

    election = get_object_or_404(
        Election,
        id=election_id
    )

    # -----------------------------------------------------
    # GET VOTER
    # -----------------------------------------------------

    voter = getattr(
        request.user,
        'voter_profile',
        None
    )

    if voter is None:

        messages.error(
            request,
            'Voter profile not found.'
        )

        return redirect('voter_dashboard')

    # =====================================================
    # ELECTION MUST STILL BE OPEN
    # =====================================================

    now = timezone.now()

    if not (
        election.status == 'ONGOING'
        and election.start_date <= now
        and election.end_date >= now
    ):

        messages.error(
            request,
            'This election is no longer open for voting.'
        )

        return redirect('election_list')

    # =====================================================
    # AADHAAR VERIFICATION
    # =====================================================

    session_aadhaar = request.session.get(
        'vote_aadhaar'
    )

    aadhaar_verified = request.session.get(
        'vote_aadhaar_verified',
        False
    )

    if not aadhaar_verified or not session_aadhaar:

        messages.error(
            request,
            'Please complete Aadhaar verification first.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # -----------------------------------------------------
    # AADHAAR MUST MATCH ACCOUNT
    # -----------------------------------------------------

    if session_aadhaar != voter.aadhaar_number:

        messages.error(
            request,
            'Aadhaar verification failed.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # =====================================================
    # CHECK ELECTION ELIGIBILITY
    # =====================================================

    if not election_allows_voter(
        election,
        session_aadhaar
    ):

        messages.error(
            request,
            'You are not eligible to vote in this election.'
        )

        return redirect(
            'election_list'
        )

    # =====================================================
    # CHECK WHETHER ALREADY VOTED
    # =====================================================

    if Vote.objects.filter(
        voter=request.user,
        election=election
    ).exists():

        messages.error(
            request,
            'You have already voted in this election.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # =====================================================
    # FIND LATEST UNUSED OTP
    # =====================================================

    vote_otp = VoteOTP.objects.filter(
        voter=request.user,
        election=election,
        is_used=False
    ).order_by(
        '-created_at'
    ).first()

    if vote_otp is None:

        messages.error(
            request,
            'No valid voting OTP found. Please try again.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # =====================================================
    # CHECK OTP EXPIRY
    # =====================================================

    expiry_time = (
        vote_otp.created_at +
        timedelta(minutes=5)
    )

    if timezone.now() > expiry_time:

        vote_otp.is_used = True

        vote_otp.save(
            update_fields=['is_used']
        )

        messages.error(
            request,
            'Voting OTP has expired. Please try again.'
        )

        return redirect(
            'election_detail',
            election_id=election.id
        )

    # =====================================================
    # POST - VERIFY OTP
    # =====================================================

    if request.method == 'POST':

        entered_otp = request.POST.get(
            'otp',
            ''
        ).strip()

        # -------------------------------------------------
        # OTP MATCH
        # -------------------------------------------------

        if entered_otp != vote_otp.otp:

            messages.error(
                request,
                'Invalid voting OTP.'
            )

            return render(
                request,
                'election/verify_vote_otp.html',
                {
                    'election': election
                }
            )

        # =================================================
        # FINAL ACCOUNT VERIFICATION
        # =================================================

        if not voter.email_verified:

            messages.error(
                request,
                'Please verify your email first.'
            )

            return redirect(
                'verify_email'
            )

        if not voter.face_verified:

            messages.error(
                request,
                'Please complete face verification first.'
            )

            return redirect(
                'face_verification'
            )

        if not voter.is_verified:

            messages.error(
                request,
                'Your voter account is not verified.'
            )

            return redirect(
                'voter_dashboard'
            )

        if not voter.is_active:

            messages.error(
                request,
                'Your voter account is inactive.'
            )

            return redirect(
                'voter_dashboard'
            )

        # =================================================
        # ELECTION MUST STILL BE OPEN
        # =================================================

        now = timezone.now()

        if not (
            election.status == 'ONGOING'
            and election.start_date <= now
            and election.end_date >= now
        ):

            vote_otp.is_used = True

            vote_otp.save(
                update_fields=['is_used']
            )

            messages.error(
                request,
                'This election is no longer open for voting.'
            )

            return redirect(
                'election_list'
            )

        # =================================================
        # CHECK ELIGIBILITY AGAIN
        # =================================================

        if not election_allows_voter(
            election,
            session_aadhaar
        ):

            vote_otp.is_used = True

            vote_otp.save(
                update_fields=['is_used']
            )

            messages.error(
                request,
                'You are not eligible to vote in this election.'
            )

            return redirect(
                'election_list'
            )

        # =================================================
        # CHECK DUPLICATE VOTE
        # =================================================

        if Vote.objects.filter(
            voter=request.user,
            election=election
        ).exists():

            vote_otp.is_used = True

            vote_otp.save(
                update_fields=['is_used']
            )

            messages.error(
                request,
                'You have already voted in this election.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        # =================================================
        # CANDIDATE MUST BELONG TO ELECTION
        # =================================================

        candidate = get_object_or_404(
            Candidate,
            id=vote_otp.candidate.id,
            election=election
        )

        # =================================================
        # RECORD VOTE
        # =================================================

        try:

            with transaction.atomic():

                Vote.objects.create(
                    voter=request.user,
                    election=election,
                    candidate=candidate
                )

                vote_otp.is_used = True

                vote_otp.save(
                    update_fields=['is_used']
                )

        except IntegrityError:

            vote_otp.is_used = True

            vote_otp.save(
                update_fields=['is_used']
            )

            messages.error(
                request,
                'You have already voted in this election.'
            )

            return redirect(
                'election_detail',
                election_id=election.id
            )

        # =================================================
        # CLEAR VOTING SESSION
        # =================================================

        request.session.pop(
            'vote_candidate_id',
            None
        )

        request.session.pop(
            'vote_election_id',
            None
        )

        request.session.pop(
            'vote_aadhaar',
            None
        )

        request.session.pop(
            'vote_aadhaar_verified',
            None
        )

        # =================================================
        # VOTE SUCCESS
        # =================================================

        return redirect(
            'vote_success',
            election_id=election.id
        )

    # =====================================================
    # DISPLAY OTP PAGE
    # =====================================================

    return render(
        request,
        'election/verify_vote_otp.html',
        {
            'election': election
        }
    )


# =========================================================
# VOTE SUCCESS
# =========================================================

@login_required(login_url='voter_login')
def vote_success(request, election_id):

    election = get_object_or_404(
        Election,
        id=election_id
    )

    vote = (
        Vote.objects
        .select_related(
            'election',
            'candidate'
        )
        .filter(
            voter=request.user,
            election=election
        )
        .first()
    )

    return render(
        request,
        'election/vote_success.html',
        {
            'election': election,
            'vote': vote,
        }
    )


# =========================================================
# PUBLIC ELECTION INFORMATION
# =========================================================

def election_information(request):

    now = timezone.now()

    ongoing_elections = Election.objects.filter(
        status='ONGOING',
        start_date__lte=now,
        end_date__gte=now
    ).order_by('end_date')

    upcoming_elections = Election.objects.filter(
        status='UPCOMING',
        start_date__gt=now
    ).order_by('start_date')

    return render(
        request,
        'election/election_information.html',
        {
            'ongoing_elections': ongoing_elections,
            'upcoming_elections': upcoming_elections,
        }
    )


# =========================================================
# PUBLIC RESULTS
# =========================================================

def public_results(request):

    elections = Election.objects.filter(
        status='CLOSED',
        results_published=True
    ).order_by('-end_date')

    return render(
        request,
        'election/public_results.html',
        {
            'elections': elections
        }
    )


# =========================================================
# PUBLIC RESULT DETAIL
# =========================================================

def public_result_detail(request, election_id):

    election = get_object_or_404(
        Election,
        id=election_id,
        status='CLOSED',
        results_published=True
    )

    candidates = election.candidates.all().order_by('name')

    results = []

    for candidate in candidates:

        vote_count = Vote.objects.filter(
            election=election,
            candidate=candidate
        ).count()

        results.append({
            'candidate': candidate,
            'vote_count': vote_count
        })

    # -----------------------------------------------------
    # FIND HIGHEST VOTE COUNT
    # -----------------------------------------------------

    if results:

        highest_votes = max(
            result['vote_count']
            for result in results
        )

        winners = [
            result['candidate']
            for result in results
            if result['vote_count'] == highest_votes
        ]

    else:

        highest_votes = 0
        winners = []

    return render(
        request,
        'election/public_result_detail.html',
        {
            'election': election,
            'results': results,
            'winners': winners,
            'highest_votes': highest_votes,
        }
    )


# =========================================================
# DOWNLOAD VOTE CONFIRMATION PDF
# =========================================================

@login_required(login_url='voter_login')
def download_vote_confirmation(request, vote_id):

    # -----------------------------------------------------
    # GET ONLY THE LOGGED-IN USER'S VOTE
    # -----------------------------------------------------

    vote = get_object_or_404(
        Vote.objects.select_related(
            'voter',
            'election',
            'candidate'
        ),
        id=vote_id,
        voter=request.user
    )

    election = vote.election
    candidate = vote.candidate

    # -----------------------------------------------------
    # CREATE PDF RESPONSE
    # -----------------------------------------------------

    response = HttpResponse(
        content_type='application/pdf'
    )

    response[
        'Content-Disposition'
    ] = (
        f'attachment; '
        f'filename="ProjectVote_Confirmation_{vote.id}.pdf"'
    )

    # -----------------------------------------------------
    # PDF DOCUMENT
    # -----------------------------------------------------

    document = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # -----------------------------------------------------
    # STYLES
    # -----------------------------------------------------

    title_style = ParagraphStyle(
        'VoteTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=29,
        alignment=TA_CENTER,
        textColor=HexColor('#12304A'),
        spaceAfter=5,
    )

    subtitle_style = ParagraphStyle(
        'VoteSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=HexColor('#60758A'),
        spaceAfter=16,
    )

    section_style = ParagraphStyle(
        'VoteSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=HexColor('#174F68'),
        spaceBefore=6,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        'VoteBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=HexColor('#34495E'),
    )

    small_style = ParagraphStyle(
        'VoteSmall',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=HexColor('#6C7F91'),
    )

    # -----------------------------------------------------
    # STORY
    # -----------------------------------------------------

    story = []

    # -----------------------------------------------------
    # HEADER
    # -----------------------------------------------------

    story.append(
        Paragraph(
            'PROJECTVOTE',
            title_style
        )
    )

    story.append(
        Paragraph(
            'SECURE • VERIFIED • TRANSPARENT',
            subtitle_style
        )
    )

    story.append(
        HRFlowable(
            width='100%',
            thickness=1,
            color=HexColor('#D5E1EA'),
            spaceAfter=16
        )
    )

    # -----------------------------------------------------
    # VOTE CONFIRMATION
    # -----------------------------------------------------

    story.append(
        Paragraph(
            'Vote Confirmation',
            section_style
        )
    )

    confirmation_table = Table(
        [
            [
                'Status',
                'VOTE SUCCESSFULLY RECORDED'
            ],
            [
                'Confirmation ID',
                f'PV-{vote.id:06d}'
            ],
        ],
        colWidths=[
            42 * mm,
            112 * mm
        ]
    )

    confirmation_table.setStyle(
        TableStyle([
            (
                'BACKGROUND',
                (0, 0),
                (0, -1),
                HexColor('#EEF5F9')
            ),

            (
                'BACKGROUND',
                (1, 0),
                (1, 0),
                HexColor('#E6F5F2')
            ),

            (
                'TEXTCOLOR',
                (0, 0),
                (0, -1),
                HexColor('#526A7D')
            ),

            (
                'TEXTCOLOR',
                (1, 0),
                (1, 0),
                HexColor('#176B63')
            ),

            (
                'TEXTCOLOR',
                (1, 1),
                (1, 1),
                HexColor('#24485F')
            ),

            (
                'FONTNAME',
                (0, 0),
                (0, -1),
                'Helvetica-Bold'
            ),

            (
                'FONTNAME',
                (1, 0),
                (1, 0),
                'Helvetica-Bold'
            ),

            (
                'FONTSIZE',
                (0, 0),
                (-1, -1),
                9.5
            ),

            (
                'GRID',
                (0, 0),
                (-1, -1),
                0.5,
                HexColor('#D5E1EA')
            ),

            (
                'VALIGN',
                (0, 0),
                (-1, -1),
                'MIDDLE'
            ),

            (
                'TOPPADDING',
                (0, 0),
                (-1, -1),
                10
            ),

            (
                'BOTTOMPADDING',
                (0, 0),
                (-1, -1),
                10
            ),
        ])
    )

    story.append(
        confirmation_table
    )

    story.append(
        Spacer(1, 15)
    )

    # -----------------------------------------------------
    # VOTER DETAILS
    # -----------------------------------------------------

    story.append(
        Paragraph(
            'Voter Details',
            section_style
        )
    )

    voter_details = Table(
        [
            [
                'Voter Name',
                vote.voter.voter_profile.full_name
            ],
            [
                'Voter ID',
                vote.voter.voter_profile.voter_id
            ],
            [
                'Email',
                vote.voter.email
            ],
        ],
        colWidths=[
            42 * mm,
            112 * mm
        ]
    )

    voter_details.setStyle(
        TableStyle([
            (
                'BACKGROUND',
                (0, 0),
                (0, -1),
                HexColor('#F4F7FA')
            ),

            (
                'TEXTCOLOR',
                (0, 0),
                (0, -1),
                HexColor('#526A7D')
            ),

            (
                'TEXTCOLOR',
                (1, 0),
                (1, -1),
                HexColor('#263E52')
            ),

            (
                'FONTNAME',
                (0, 0),
                (0, -1),
                'Helvetica-Bold'
            ),

            (
                'FONTNAME',
                (1, 0),
                (1, -1),
                'Helvetica'
            ),

            (
                'FONTSIZE',
                (0, 0),
                (-1, -1),
                9.5
            ),

            (
                'GRID',
                (0, 0),
                (-1, -1),
                0.5,
                HexColor('#DDE5EB')
            ),

            (
                'VALIGN',
                (0, 0),
                (-1, -1),
                'MIDDLE'
            ),

            (
                'TOPPADDING',
                (0, 0),
                (-1, -1),
                9
            ),

            (
                'BOTTOMPADDING',
                (0, 0),
                (-1, -1),
                9
            ),
        ])
    )

    story.append(
        voter_details
    )

    story.append(
        Spacer(1, 15)
    )

    # -----------------------------------------------------
    # ELECTION DETAILS
    # -----------------------------------------------------

    story.append(
        Paragraph(
            'Election Details',
            section_style
        )
    )

    election_details = Table(
        [
            [
                'Election',
                election.name
            ],
            [
                'Candidate Selected',
                candidate.name
            ],
            [
                'Party',
                candidate.party or 'Independent'
            ],
            [
                'Vote Recorded',
                timezone.localtime(
                    vote.voted_at
                ).strftime(
                    '%d %B %Y, %I:%M %p'
                )
            ],
        ],
        colWidths=[
            42 * mm,
            112 * mm
        ]
    )

    election_details.setStyle(
        TableStyle([
            (
                'BACKGROUND',
                (0, 0),
                (0, -1),
                HexColor('#F4F7FA')
            ),

            (
                'TEXTCOLOR',
                (0, 0),
                (0, -1),
                HexColor('#526A7D')
            ),

            (
                'TEXTCOLOR',
                (1, 0),
                (1, -1),
                HexColor('#263E52')
            ),

            (
                'FONTNAME',
                (0, 0),
                (0, -1),
                'Helvetica-Bold'
            ),

            (
                'FONTNAME',
                (1, 0),
                (1, -1),
                'Helvetica'
            ),

            (
                'FONTSIZE',
                (0, 0),
                (-1, -1),
                9.5
            ),

            (
                'GRID',
                (0, 0),
                (-1, -1),
                0.5,
                HexColor('#DDE5EB')
            ),

            (
                'VALIGN',
                (0, 0),
                (-1, -1),
                'MIDDLE'
            ),

            (
                'TOPPADDING',
                (0, 0),
                (-1, -1),
                9
            ),

            (
                'BOTTOMPADDING',
                (0, 0),
                (-1, -1),
                9
            ),
        ])
    )

    story.append(
        election_details
    )

    story.append(
        Spacer(1, 20)
    )

    # -----------------------------------------------------
    # CONFIRMATION MESSAGE
    # -----------------------------------------------------

    confirmation_message = Table(
        [[
            Paragraph(
                '<b>Confirmation</b><br/>'
                'This document confirms that your vote was '
                'successfully recorded in ProjectVote. '
                'Keep this confirmation for your personal records.',
                body_style
            )
        ]],
        colWidths=[
            154 * mm
        ]
    )

    confirmation_message.setStyle(
        TableStyle([
            (
                'BACKGROUND',
                (0, 0),
                (-1, -1),
                HexColor('#F0F7F8')
            ),

            (
                'BOX',
                (0, 0),
                (-1, -1),
                0.8,
                HexColor('#B8D9DE')
            ),

            (
                'LEFTPADDING',
                (0, 0),
                (-1, -1),
                13
            ),

            (
                'RIGHTPADDING',
                (0, 0),
                (-1, -1),
                13
            ),

            (
                'TOPPADDING',
                (0, 0),
                (-1, -1),
                12
            ),

            (
                'BOTTOMPADDING',
                (0, 0),
                (-1, -1),
                12
            ),
        ])
    )

    story.append(
        confirmation_message
    )

    story.append(
        Spacer(1, 25)
    )

    # -----------------------------------------------------
    # FOOTER
    # -----------------------------------------------------

    story.append(
        Paragraph(
            'Generated by ProjectVote • Academic Prototype',
            small_style
        )
    )

    story.append(
        Paragraph(
            'This confirmation is a record of a vote submitted '
            'through the ProjectVote system.',
            small_style
        )
    )

    # -----------------------------------------------------
    # BUILD PDF
    # -----------------------------------------------------

    document.build(story)

    return response