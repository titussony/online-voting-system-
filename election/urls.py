from django.urls import path

from . import views


urlpatterns = [

    path(
        'information/',
        views.election_information,
        name='election_information'
    ),

    path(
        '',
        views.election_list,
        name='election_list'
    ),

    path(
        '<int:election_id>/vote-face-verification/',
        views.vote_face_verification,
        name='vote_face_verification'
    ),

    path(
        '<int:election_id>/',
        views.election_detail,
        name='election_detail'
    ),

    path(
        '<int:election_id>/verify-vote-otp/',
        views.verify_vote_otp,
        name='verify_vote_otp'
    ),

    path(
        '<int:election_id>/vote-success/',
        views.vote_success,
        name='vote_success'
    ),

    path(
        'results/',
        views.public_results,
        name='public_results'
    ),

    path(
        'results/<int:election_id>/',
        views.public_result_detail,
        name='public_result_detail'
    ),

    # Vote confirmation PDF
    path(
        'vote/<int:vote_id>/confirmation/',
        views.download_vote_confirmation,
        name='download_vote_confirmation'
    ),
]