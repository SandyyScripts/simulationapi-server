from django.urls import path
from .views import *

urlpatterns = [
    path('ride_simulator/', RideBookingAPIView.as_view(), name='ride-simulator-api'),
    path('ride_assignment/', RideSimulatorAPIView.as_view(), name='ride-assignment-api'),
    path('rate-limited-endpoint/', rate_limited_view, name='rate-limited-view'),
]