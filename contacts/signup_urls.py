""" Signup URLs for the contacts app """

from django.urls import path

from . import views

urlpatterns = [
    path("", views.signup, name="signup"),
]
