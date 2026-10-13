from django.urls import path
from . import views


urlpatterns = [

    path(
        '',
        views.home,
        name='home'
    ),

    path(
        'register/',
        views.register,
        name='register'
    ),

    path(
        'login/',
        views.voter_login,
        name='voter_login'
    ),

    path(
        'dashboard/',
        views.voter_dashboard,
        name='voter_dashboard'
    ),

    path(
        'logout/',
        views.voter_logout,
        name='voter_logout'
    ),

    path(
        'verify-email/',
        views.verify_email,
        name='verify_email'
    ),

    path(
        'resend-otp/',
        views.resend_email_otp,
        name='resend_email_otp'
    ),

    path(
        'face-verification/',
        views.face_verification,
        name='face_verification'
    ),
]