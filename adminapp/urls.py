from django.urls import path

from . import views


urlpatterns = [

    # Admin authentication

    path(
        'login/',
        views.admin_login,
        name='admin_login'
    ),

    path(
        'dashboard/',
        views.admin_dashboard,
        name='admin_dashboard'
    ),


    # Election management

    path(
        'elections/',
        views.manage_elections,
        name='manage_elections'
    ),

    path(
        'elections/create/',
        views.create_election,
        name='create_election'
    ),

    path(
        'elections/<int:election_id>/edit/',
        views.edit_election,
        name='edit_election'
    ),

    path(
    'elections/<int:election_id>/download-eligibility/',
    views.download_eligibility_csv,
    name='download_eligibility_csv'
    ),

    path(
        'elections/<int:election_id>/delete/',
        views.delete_election,
        name='delete_election'
    ),

    path(
        'elections/<int:election_id>/start/',
        views.start_election,
        name='start_election'
    ),

    path(
        'elections/<int:election_id>/close/',
        views.close_election,
        name='close_election'
    ),


    # Candidate management

    path(
        'candidates/',
        views.manage_candidates,
        name='manage_candidates'
    ),

    path(
        'candidates/create/',
        views.create_candidate,
        name='create_candidate'
    ),

    path(
        'candidates/<int:candidate_id>/edit/',
        views.edit_candidate,
        name='edit_candidate'
    ),

    path(
        'candidates/<int:candidate_id>/delete/',
        views.delete_candidate,
        name='delete_candidate'
    ),


    # Results

    path(
        'results/',
        views.view_results,
        name='view_results'
    ),

    path(
        'results/<int:election_id>/publish/',
        views.publish_results,
        name='publish_results'
    ),


    # Logout

    path(
        'logout/',
        views.admin_logout,
        name='admin_logout'
    ),
   
    path(
    'election-history/',
    views.election_history,
    name='election_history'
   ),




]