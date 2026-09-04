from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone

class City(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name
        
    class Meta:
        verbose_name_plural = "Cities"

class Movie(models.Model):
    CERTIFICATION_CHOICES = [
        ('U', 'Unrestricted'),
        ('UA', 'Unrestricted but with parental guidance'),
        ('A', 'Adults only'),
        ('S', 'Specialized audience'),
    ]
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="movies/posters/", blank=True, null=True)
    genre = models.CharField(max_length=255, help_text="Comma separated genres, e.g., Action, Sci-Fi")
    language = models.CharField(max_length=100)
    release_date = models.DateField()
    duration = models.IntegerField(help_text="Duration in minutes")
    age_certification = models.CharField(max_length=2, choices=CERTIFICATION_CHOICES, default='UA')
    youtube_trailer_url = models.URLField(blank=True, null=True)
    popularity_score = models.IntegerField(default=0)
    
    # We remove static rating and make it a property based on reviews, but can keep an average field for caching
    average_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    cast = models.TextField()
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class MoviePoster(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='additional_posters')
    image = models.ImageField(upload_to="movies/gallery/")
    
    def __str__(self):
        return f"Poster for {self.movie.name}"

class MovieReview(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    text = models.TextField()
    is_verified_viewer = models.BooleanField(default=False)
    is_reported = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('movie', 'user')
        
    def __str__(self):
        return f"{self.user.username}'s review for {self.movie.name}"

class Theater(models.Model):
    name = models.CharField(max_length=255)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='theaters')
    address = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.name}, {self.city.name}"

class Screen(models.Model):
    name = models.CharField(max_length=50) # e.g. Screen 1, IMAX
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='screens')
    
    def __str__(self):
        return f"{self.name} - {self.theater.name}"

class Seat(models.Model):
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.CharField(max_length=10) # e.g. A1, B2
    row = models.CharField(max_length=5) # e.g. A, B, C
    seat_type = models.CharField(max_length=20, default='Standard') # e.g. Standard, Premium, Recliner
    
    def __str__(self):
        return f"{self.seat_number} in {self.screen.name}"
        
    class Meta:
        unique_together = ('screen', 'seat_number')

class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='shows')
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, related_name='shows')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    ticket_price = models.DecimalField(max_digits=8, decimal_places=2)
    
    def __str__(self):
        return f"{self.movie.name} at {self.screen} on {self.start_time.strftime('%Y-%m-%d %H:%M')}"

class Booking(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled')
    ]
    
    booking_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Booking {self.booking_id} by {self.user.username}"

class SeatReservation(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved (Locked)'),
        ('BOOKED', 'Booked')
    ]
    
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='reservations')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='reserved_seats')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='AVAILABLE')
    reserved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('show', 'seat')
        
    def __str__(self):
        return f"{self.seat.seat_number} for {self.show} - {self.status}"
        
    @property
    def is_locked(self):
        if self.status == 'RESERVED' and self.reserved_at:
            # Check if reserved within last 2 minutes
            return timezone.now() < self.reserved_at + timezone.timedelta(minutes=2)
        return False

class Payment(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    provider = models.CharField(max_length=50, default='stripe')
    status = models.CharField(max_length=50) # e.g. requires_payment_method, succeeded, failed
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment {self.transaction_id} for Booking {self.booking.booking_id}"