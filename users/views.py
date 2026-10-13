import os
import base64
import random
import cv2

from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.core.files.base import ContentFile

from .forms import VoterRegistrationForm
from .models import EmailOTP


# =========================================================
# OPENCV FACE RECOGNITION MODEL PATHS
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

FACE_DETECTION_MODEL = os.path.join(
    BASE_DIR,
    'models',
    'face_detection_yunet_2023mar.onnx'
)

FACE_RECOGNITION_MODEL = os.path.join(
    BASE_DIR,
    'models',
    'face_recognition_sface_2021dec.onnx'
)


# =========================================================
# HOME
# =========================================================

def home(request):

    return render(
        request,
        'home.html'
    )


# =========================================================
# VOTER REGISTRATION
# =========================================================

def register(request):

    if request.method == 'POST':

        form = VoterRegistrationForm(
            request.POST
        )

        captured_photo = request.POST.get(
            'captured_photo'
        )

        # ---------------------------------------------
        # PHOTO REQUIRED
        # ---------------------------------------------

        if not captured_photo:

            messages.error(
                request,
                'Please capture your photo before registering.'
            )

            return render(
                request,
                'users/register.html',
                {
                    'form': form
                }
            )

        # ---------------------------------------------
        # VALIDATE FORM
        # ---------------------------------------------

        if form.is_valid():

            try:

                with transaction.atomic():

                    voter = form.save(
                        commit=False
                    )

                    username = (
                        form.cleaned_data['username']
                    )

                    email = (
                        form.cleaned_data['email']
                    )

                    password = (
                        form.cleaned_data['password']
                    )

                    # ---------------------------------
                    # CREATE DJANGO USER
                    # ---------------------------------

                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password
                    )

                    voter.user = user

                    # ---------------------------------
                    # CONVERT CAMERA IMAGE
                    # ---------------------------------

                    format_data, image_data = (
                        captured_photo.split(
                            ';base64,'
                        )
                    )

                    image_data = base64.b64decode(
                        image_data
                    )

                    # ---------------------------------
                    # SAVE REGISTRATION PHOTO
                    # ---------------------------------

                    voter.photo.save(
                        f'{username}_registration.jpg',
                        ContentFile(image_data),
                        save=False
                    )

                    # ---------------------------------
                    # INITIAL VERIFICATION STATUS
                    # ---------------------------------

                    voter.email_verified = False
                    voter.face_verified = False
                    voter.is_verified = False

                    voter.save()

                messages.success(
                    request,
                    'Registration successful. You can now log in.'
                )

                return redirect(
                    'voter_login'
                )

            except Exception as error:

                messages.error(
                    request,
                    'Registration failed. Please try again.'
                )

                print(
                    'Registration error:',
                    error
                )

    else:

        form = VoterRegistrationForm()

    return render(
        request,
        'users/register.html',
        {
            'form': form
        }
    )


# =========================================================
# SEND EMAIL OTP
# =========================================================

def send_email_otp(user):

    otp = str(
        random.randint(
            100000,
            999999
        )
    )

    # ---------------------------------------------
    # INVALIDATE PREVIOUS OTPs
    # ---------------------------------------------

    EmailOTP.objects.filter(
        user=user,
        is_used=False
    ).update(
        is_used=True
    )

    # ---------------------------------------------
    # CREATE NEW OTP
    # ---------------------------------------------

    EmailOTP.objects.create(
        user=user,
        otp=otp
    )

    # ---------------------------------------------
    # SEND EMAIL
    # ---------------------------------------------

    send_mail(

        subject='ProjectVote Email Verification OTP',

        message=(
            f'Your ProjectVote verification OTP is: {otp}\n\n'
            'This OTP is valid for 5 minutes.'
        ),

        from_email=None,

        recipient_list=[
            user.email
        ],

        fail_silently=False,
    )


# =========================================================
# VOTER LOGIN
# =========================================================

def voter_login(request):

    if request.method == 'POST':

        username = request.POST.get(
            'username'
        )

        password = request.POST.get(
            'password'
        )

        # ---------------------------------------------
        # AUTHENTICATE
        # ---------------------------------------------

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:

            messages.error(
                request,
                'Invalid username or password.'
            )

            return render(
                request,
                'users/login.html'
            )

        # ---------------------------------------------
        # CHECK ACTIVE STATUS
        # ---------------------------------------------

        if not user.is_active:

            messages.error(
                request,
                'Your account is inactive.'
            )

            return redirect(
                'voter_login'
            )

        # ---------------------------------------------
        # GET VOTER PROFILE
        # ---------------------------------------------

        try:

            voter = user.voter_profile

        except Exception:

            messages.error(
                request,
                'Voter profile not found.'
            )

            return redirect(
                'voter_login'
            )

        # ---------------------------------------------
        # LOGIN
        # ---------------------------------------------

        login(
            request,
            user
        )

        # =============================================
        # STEP 1 — EMAIL VERIFICATION
        # =============================================

        if not voter.email_verified:

            send_email_otp(
                user
            )

            return redirect(
                'verify_email'
            )

        # =============================================
        # STEP 2 — FACE VERIFICATION
        # =============================================

        if not voter.face_verified:

            return redirect(
                'face_verification'
            )

        # =============================================
        # STEP 3 — FULLY VERIFIED
        # =============================================

        return redirect(
            'voter_dashboard'
        )

    return render(
        request,
        'users/login.html'
    )


# =========================================================
# EMAIL OTP VERIFICATION
# =========================================================

@login_required(login_url='voter_login')
def verify_email(request):

    voter = request.user.voter_profile

    # ---------------------------------------------
    # EMAIL ALREADY VERIFIED
    # ---------------------------------------------

    if voter.email_verified:

        if not voter.face_verified:

            return redirect(
                'face_verification'
            )

        return redirect(
            'voter_dashboard'
        )

    # ---------------------------------------------
    # OTP SUBMISSION
    # ---------------------------------------------

    if request.method == 'POST':

        entered_otp = request.POST.get(
            'otp'
        )

        # ---------------------------------------------
        # GET LATEST UNUSED OTP
        # ---------------------------------------------

        otp_record = EmailOTP.objects.filter(
            user=request.user,
            is_used=False
        ).order_by(
            '-created_at'
        ).first()

        if otp_record is None:

            messages.error(
                request,
                'No valid OTP found. Please request a new OTP.'
            )

            return redirect(
                'verify_email'
            )

        # ---------------------------------------------
        # CHECK OTP EXPIRY
        # ---------------------------------------------

        expiry_time = (
            otp_record.created_at
            +
            timedelta(minutes=5)
        )

        if timezone.now() > expiry_time:

            otp_record.is_used = True

            otp_record.save()

            messages.error(
                request,
                'OTP has expired. Please request a new OTP.'
            )

            return redirect(
                'verify_email'
            )

        # ---------------------------------------------
        # CHECK OTP
        # ---------------------------------------------

        if entered_otp == otp_record.otp:

            otp_record.is_used = True

            otp_record.save()

            voter.email_verified = True

            voter.save(
                update_fields=[
                    'email_verified'
                ]
            )

            messages.success(
                request,
                'Email verified successfully.'
            )

            return redirect(
                'face_verification'
            )

        messages.error(
            request,
            'Invalid OTP.'
        )

    return render(
        request,
        'users/verify_email.html'
    )


# =========================================================
# RESEND EMAIL OTP
# =========================================================

@login_required(login_url='voter_login')
def resend_email_otp(request):

    voter = request.user.voter_profile

    # ---------------------------------------------
    # ALREADY VERIFIED
    # ---------------------------------------------

    if voter.email_verified:

        if not voter.face_verified:

            return redirect(
                'face_verification'
            )

        return redirect(
            'voter_dashboard'
        )

    # ---------------------------------------------
    # RESEND
    # ---------------------------------------------

    if request.method == 'POST':

        send_email_otp(
            request.user
        )

        messages.success(
            request,
            'A new OTP has been sent to your email.'
        )

    return redirect(
        'verify_email'
    )


# =========================================================
# OPENCV FACE COMPARISON
# =========================================================

def compare_faces(
    reference_image_path,
    live_image_path
):

    # ---------------------------------------------
    # CHECK MODEL FILES
    # ---------------------------------------------

    if not os.path.exists(
        FACE_DETECTION_MODEL
    ):

        raise FileNotFoundError(
            'YuNet face detection model not found.'
        )

    if not os.path.exists(
        FACE_RECOGNITION_MODEL
    ):

        raise FileNotFoundError(
            'SFace face recognition model not found.'
        )

    # ---------------------------------------------
    # READ IMAGES
    # ---------------------------------------------

    reference_image = cv2.imread(
        reference_image_path
    )

    live_image = cv2.imread(
        live_image_path
    )

    if reference_image is None:

        raise ValueError(
            'Could not read the registered photo.'
        )

    if live_image is None:

        raise ValueError(
            'Could not read the live camera photo.'
        )

    # ---------------------------------------------
    # CREATE YUNET FACE DETECTOR
    # ---------------------------------------------

    detector = cv2.FaceDetectorYN.create(

        FACE_DETECTION_MODEL,

        "",

        (
            320,
            320
        ),

        0.9,

        0.3,

        5000
    )

    # =============================================
    # DETECT FACE IN REGISTRATION PHOTO
    # =============================================

    detector.setInputSize(
        (
            reference_image.shape[1],
            reference_image.shape[0]
        )
    )

    _, reference_faces = detector.detect(
        reference_image
    )

    if reference_faces is None:

        raise ValueError(
            'No face detected in the registered photo.'
        )

    if len(reference_faces) != 1:

        raise ValueError(
            'Registered photo must contain exactly one face.'
        )

    # =============================================
    # DETECT FACE IN LIVE PHOTO
    # =============================================

    detector.setInputSize(
        (
            live_image.shape[1],
            live_image.shape[0]
        )
    )

    _, live_faces = detector.detect(
        live_image
    )

    if live_faces is None:

        raise ValueError(
            'No face detected in the live camera image.'
        )

    if len(live_faces) != 1:

        raise ValueError(
            'Please make sure exactly one face is visible.'
        )

    # =============================================
    # CREATE SFACE RECOGNIZER
    # =============================================

    recognizer = cv2.FaceRecognizerSF.create(

        FACE_RECOGNITION_MODEL,

        ""
    )

    # =============================================
    # ALIGN REGISTRATION FACE
    # =============================================

    reference_aligned = recognizer.alignCrop(

        reference_image,

        reference_faces[0]
    )

    # =============================================
    # ALIGN LIVE FACE
    # =============================================

    live_aligned = recognizer.alignCrop(

        live_image,

        live_faces[0]
    )

    # =============================================
    # CREATE FACE FEATURES
    # =============================================

    reference_feature = recognizer.feature(
        reference_aligned
    )

    live_feature = recognizer.feature(
        live_aligned
    )

    # =============================================
    # COMPARE USING COSINE SIMILARITY
    # =============================================

    cosine_score = recognizer.match(

        reference_feature,

        live_feature,

        cv2.FaceRecognizerSF_FR_COSINE
    )

    # ---------------------------------------------
    # SFACE COSINE THRESHOLD
    # ---------------------------------------------

    threshold = 0.363

    is_match = (
        cosine_score >= threshold
    )

    return (
        is_match,
        float(cosine_score)
    )


# =========================================================
# FACE VERIFICATION
# =========================================================

@login_required(login_url='voter_login')
def face_verification(request):

    voter = request.user.voter_profile

    # =============================================
    # EMAIL VERIFICATION REQUIRED
    # =============================================

    if not voter.email_verified:

        return redirect(
            'verify_email'
        )

    # =============================================
    # ALREADY FACE VERIFIED
    # =============================================

    if voter.face_verified:

        return redirect(
            'voter_dashboard'
        )

    # =============================================
    # GET → SHOW CAMERA
    # =============================================

    if request.method == 'GET':

        return render(
            request,
            'users/face_verification.html'
        )

    # =============================================
    # POST → RECEIVE LIVE PHOTO
    # =============================================

    if request.method == 'POST':

        live_photo = request.FILES.get(
            'live_photo'
        )

        # ---------------------------------------------
        # CHECK LIVE PHOTO
        # ---------------------------------------------

        if live_photo is None:

            return JsonResponse({

                'success': False,

                'message':
                    'No camera image received.'
            })

        # ---------------------------------------------
        # CHECK REGISTERED PHOTO
        # ---------------------------------------------

        if not voter.photo:

            return JsonResponse({

                'success': False,

                'message':
                    'No registration photo found.'
            })

        # ---------------------------------------------
        # TEMPORARY DIRECTORY
        # ---------------------------------------------

        temp_directory = os.path.join(

            BASE_DIR,

            'media',

            'face_temp'
        )

        os.makedirs(

            temp_directory,

            exist_ok=True
        )

        # ---------------------------------------------
        # TEMPORARY FILE
        # ---------------------------------------------

        temp_path = os.path.join(

            temp_directory,

            f'{request.user.id}_live.jpg'
        )

        try:

            # =========================================
            # SAVE LIVE PHOTO
            # =========================================

            with open(

                temp_path,

                'wb'

            ) as destination:

                for chunk in live_photo.chunks():

                    destination.write(
                        chunk
                    )

            # =========================================
            # GET REGISTERED PHOTO
            # =========================================

            registration_photo = (
                voter.photo.path
            )

            # =========================================
            # COMPARE FACES
            # =========================================

            verified, score = compare_faces(

                registration_photo,

                temp_path
            )

            print(
                f'Face similarity score: {score:.4f}'
            )

            # =========================================
            # FACE MATCH
            # =========================================

            if verified:

                voter.face_verified = True

                voter.is_verified = True

                voter.save(

                    update_fields=[

                        'face_verified',

                        'is_verified'
                    ]
                )

                return JsonResponse({

                    'success': True,

                    'message':
                        'Face verification successful.'
                })

            # =========================================
            # FACE DOES NOT MATCH
            # =========================================

            return JsonResponse({

                'success': False,

                'message':
                    'Face does not match the registered photo. '
                    'Please try again.'
            })

        except Exception as error:

            print(
                '================================='
            )

            print(
                'FACE VERIFICATION ERROR'
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
                    'Please make sure your face is '
                    'clearly visible and try again.'
            })

        finally:

            # =========================================
            # DELETE TEMPORARY IMAGE
            # =========================================

            if os.path.exists(
                temp_path
            ):

                os.remove(
                    temp_path
                )

    return JsonResponse({

        'success': False,

        'message':
            'Invalid request.'
    })


# =========================================================
# VOTER DASHBOARD
# =========================================================

@login_required(login_url='voter_login')
def voter_dashboard(request):

    voter = request.user.voter_profile

    if not voter.email_verified:
        return redirect('verify_email')

    if not voter.face_verified:
        return redirect('face_verification')

    if not voter.is_verified:
        return redirect('face_verification')

    from election.models import Election
    from django.utils import timezone

    now = timezone.now()

    ongoing_elections = Election.objects.filter(
        status='ONGOING',
        start_date__lte=now,
        end_date__gte=now
    ).order_by('end_date')

    return render(
        request,
        'users/dashboard.html',
        {
            'voter_profile': voter,
            'ongoing_elections': ongoing_elections
        }
    )


# =========================================================
# LOGOUT
# =========================================================

def voter_logout(request):

    logout(
        request
    )

    return redirect(
        'voter_login'
    )