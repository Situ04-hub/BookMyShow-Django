from django.contrib import admin
from .models import City, Movie, MoviePoster, MovieReview, Theater, Screen, Seat, Show, Booking, SeatReservation, Payment

class MoviePosterInline(admin.TabularInline):
    model = MoviePoster
    extra = 1

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('name', 'genre', 'language', 'release_date', 'age_certification', 'average_rating')
    search_fields = ('name', 'genre', 'language')
    list_filter = ('language', 'age_certification', 'genre')
    inlines = [MoviePosterInline]

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ('name', 'city')
    search_fields = ('name', 'city__name')
    list_filter = ('city',)

@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ('name', 'theater')
    list_filter = ('theater__city', 'theater')

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('seat_number', 'row', 'seat_type', 'screen')
    list_filter = ('screen__theater', 'seat_type')
    search_fields = ('seat_number',)

@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = ('movie', 'screen', 'start_time', 'end_time', 'ticket_price')
    list_filter = ('start_time', 'movie', 'screen__theater')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'user', 'show', 'total_amount', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'created_at')
    search_fields = ('booking_id', 'user__username')

@admin.register(SeatReservation)
class SeatReservationAdmin(admin.ModelAdmin):
    list_display = ('seat', 'show', 'status', 'user', 'reserved_at')
    list_filter = ('status', 'show__movie')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'booking', 'provider', 'status', 'amount')
    list_filter = ('status', 'provider')
    
@admin.register(MovieReview)
class MovieReviewAdmin(admin.ModelAdmin):
    list_display = ('movie', 'user', 'rating', 'is_verified_viewer', 'is_reported', 'created_at')
    list_filter = ('rating', 'is_reported', 'is_verified_viewer')