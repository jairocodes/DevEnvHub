from django.http import HttpResponse
from django.urls import path


def hello(request):
    return HttpResponse("Hello from DevEnv Hub (django template)\n")


urlpatterns = [
    path("", hello),
]
