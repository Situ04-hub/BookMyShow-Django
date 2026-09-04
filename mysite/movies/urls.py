from django.urls import path
from . import views

urlpatterns = [
    path('', views.movie_list, name='movie_list'),
    path('<int:movie_id>/', views.movie_detail, name='movie_detail'),
    path('show/<int:show_id>/seats/', views.show_seats, name='show_seats'),
    path('booking/<str:booking_id>/checkout/', views.checkout, name='checkout'),
    path('booking/<str:booking_id>/success/', views.payment_success, name='payment_success'),
    path('booking/<str:booking_id>/cancel/', views.payment_cancel, name='payment_cancel'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('my-bookings/', views.booking_history, name='booking_history'),
]