from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from .models import Movie, Show, Seat, SeatReservation, Booking, Payment, MovieReview, Theater, City
from .tasks import generate_and_send_ticket
import stripe
import json
import logging
from django.db.models import Q, Count, Avg, Sum, F
from django.db.models.functions import TruncDate

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

# --- 1. Movie Discovery ---

def movie_list(request):
    movies = Movie.objects.all().order_by('-release_date')
    
    # Filters
    query = request.GET.get('q')
    genre = request.GET.get('genre')
    language = request.GET.get('language')
    city_id = request.GET.get('city')
    
    if query:
        movies = movies.filter(Q(name__icontains=query) | Q(cast__icontains=query))
    if genre:
        movies = movies.filter(genre__icontains=genre)
    if language:
        movies = movies.filter(language__icontains=language)
    if city_id:
        movies = movies.filter(shows__screen__theater__city_id=city_id).distinct()
        
    # Sorting
    sort = request.GET.get('sort')
    if sort == 'popularity':
        movies = movies.order_by('-popularity_score')
    elif sort == 'rating':
        movies = movies.order_by('-average_rating')
        
    # Pagination
    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    cities = City.objects.all()
    
    return render(request, 'movies/movie_list.html', {
        'page_obj': page_obj,
        'cities': cities,
        'total_count': movies.count()
    })

def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    shows = Show.objects.filter(movie=movie, start_time__gte=timezone.now()).select_related('screen__theater')
    reviews = movie.reviews.all().order_by('-created_at')
    
    # Recommendations based on genre
    similar_movies = Movie.objects.filter(genre__icontains=movie.genre.split(',')[0]).exclude(id=movie.id)[:4]
    
    return render(request, 'movies/movie_detail.html', {
        'movie': movie,
        'shows': shows,
        'reviews': reviews,
        'similar_movies': similar_movies
    })

# --- 2. Smart Seat Reservation ---

@login_required
def show_seats(request, show_id):
    show = get_object_or_404(Show, id=show_id)
    
    if request.method == 'POST':
        seat_ids = request.POST.getlist('seats')
        if not seat_ids:
            return JsonResponse({'error': 'No seats selected'}, status=400)
            
        try:
            with transaction.atomic():
                # Select related seats with a FOR UPDATE lock to prevent concurrent modifications
                seats = Seat.objects.select_for_update().filter(
                    screen=show.screen, id__in=seat_ids
                )
                
                # Verify all seats exist for this show's screen
                if len(seats) != len(seat_ids):
                    return JsonResponse({'error': 'Invalid seats selected'}, status=400)
                
                # Check availability
                existing_res = SeatReservation.objects.filter(show=show, seat__in=seats)
                res_map = {res.seat_id: res for res in existing_res}
                
                reservations_to_save = []
                for seat in seats:
                    res = res_map.get(seat.id)
                    if res:
                        if res.status == 'BOOKED' or res.is_locked:
                            return JsonResponse({'error': f'Seat {seat.seat_number} is no longer available'}, status=400)
                    else:
                        res = SeatReservation(show=show, seat=seat, status='AVAILABLE')
                    reservations_to_save.append(res)
                
                # Create a pending booking
                total_amount = len(seat_ids) * show.ticket_price
                booking = Booking.objects.create(
                    user=request.user,
                    show=show,
                    total_amount=total_amount,
                    payment_status='PENDING'
                )
                
                # Update reservations to locked
                now = timezone.now()
                for res in reservations_to_save:
                    res.status = 'PENDING'
                    res.reserved_at = now
                    res.user = request.user
                    res.booking = booking
                
                SeatReservation.objects.bulk_update(
                    [r for r in reservations_to_save if r.id], 
                    ['status', 'reserved_at', 'user', 'booking']
                )
                SeatReservation.objects.bulk_create(
                    [r for r in reservations_to_save if not r.id]
                )
                    
                return JsonResponse({'success': True, 'booking_id': booking.booking_id})
            
        except Exception as e:
            logger.error(f"Error during seat reservation: {str(e)}")
            return JsonResponse({'error': 'An error occurred during reservation'}, status=500)
            
    # GET request - load seat map
    seats = Seat.objects.filter(screen=show.screen).order_by('row', 'seat_number')
    reservations = SeatReservation.objects.filter(show=show)
    res_dict = {res.seat_id: res for res in reservations}
    
    seat_data = []
    for seat in seats:
        res = res_dict.get(seat.id)
        status = res.status if res else 'AVAILABLE'
        is_locked = res and res.status == 'PENDING'
        seat_data.append({
            'seat': seat,
            'status': status,
            'is_locked': is_locked,
        })
        
    return render(request, 'movies/seat_map.html', {
        'show': show,
        'reservations': seat_data
    })

# --- 3. Payment Integration ---

@login_required
def checkout(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    
    if booking.payment_status != 'PENDING':
        return redirect('movie_list') # Or error page
        
    if request.method == 'POST':
        # Bypass Stripe if using dummy key for local testing
        if settings.STRIPE_SECRET_KEY == 'sk_test_dummy':
            try:
                with transaction.atomic():
                    booking_to_update = Booking.objects.select_for_update().get(booking_id=booking_id)
                    if booking_to_update.payment_status == 'PENDING':
                        booking_to_update.payment_status = 'CONFIRMED'
                        booking_to_update.save()
                        SeatReservation.objects.filter(booking=booking_to_update).update(status='BOOKED')
                        Payment.objects.create(
                            booking=booking_to_update,
                            transaction_id='dummy_txn_123',
                            status='succeeded',
                            amount=booking_to_update.total_amount
                        )
                        # Trigger async task if celery is running, or just call it directly for now (optional)
                        # generate_and_send_ticket.delay(booking_to_update.booking_id)
            except Exception as e:
                logger.error(str(e))
                return JsonResponse({'error': 'Failed to process dummy payment.'}, status=500)
                
            return JsonResponse({
                'success': True, 
                'redirect_url': request.build_absolute_uri(f'/movies/booking/{booking.booking_id}/success/')
            })
            
        # Create Stripe checkout session
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd', # Update currency as needed
                        'product_data': {
                            'name': f"{booking.show.movie.name} - Tickets",
                        },
                        'unit_amount': int(booking.total_amount * 100), # Stripe expects cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(f'/movies/booking/{booking.booking_id}/success/'),
                cancel_url=request.build_absolute_uri(f'/movies/booking/{booking.booking_id}/cancel/'),
                client_reference_id=booking.booking_id,
            )
            return JsonResponse({'id': session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return render(request, 'movies/checkout.html', {'booking': booking, 'stripe_public_key': settings.STRIPE_PUBLIC_KEY})

def payment_success(request, booking_id):
    # The actual confirmation happens in the webhook. This is just for UI.
    return render(request, 'movies/payment_success.html', {'booking_id': booking_id})

def payment_cancel(request, booking_id):
    return render(request, 'movies/payment_cancel.html', {'booking_id': booking_id})

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        booking_id = session.get('client_reference_id')
        transaction_id = session.get('payment_intent')
        
        if booking_id:
            try:
                with transaction.atomic():
                    booking = Booking.objects.select_for_update().get(booking_id=booking_id)
                    
                    if booking.payment_status == 'PENDING':
                        booking.payment_status = 'CONFIRMED'
                        booking.save()
                        
                        # Update seats to BOOKED
                        SeatReservation.objects.filter(booking=booking).update(status='BOOKED')
                        
                        # Create Payment record
                        Payment.objects.create(
                            booking=booking,
                            transaction_id=transaction_id,
                            status='succeeded',
                            amount=booking.total_amount
                        )
                        
                        # Trigger async PDF generation and email
                        generate_and_send_ticket.delay(booking.booking_id)
            except Booking.DoesNotExist:
                logger.error(f"Webhook error: Booking {booking_id} not found")

    return HttpResponse(status=200)

# --- 4. Admin Dashboard ---

import csv
from django.http import HttpResponse

@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    # Optimize aggregations using Django ORM
    
    # Revenue Trends
    daily_revenue = Booking.objects.filter(payment_status='CONFIRMED').annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total=Sum('total_amount')
    ).order_by('-date')[:30]
    
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="revenue_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Date', 'Revenue'])
        for rev in daily_revenue:
            writer.writerow([rev['date'], rev['total']])
        return response
    
    # Theater Occupancy (Booked seats / Total Seats)
    # This requires a more complex query or subqueries. For simplicity here:
    theater_stats = Theater.objects.annotate(
        total_shows=Count('screens__shows', distinct=True),
        total_bookings=Count('screens__shows__reservations', filter=Q(screens__shows__reservations__status='BOOKED'), distinct=True)
    )
    
    # Most Booked Movies
    top_movies = Movie.objects.annotate(
        booking_count=Count('shows__reservations', filter=Q(shows__reservations__status='BOOKED'))
    ).order_by('-booking_count')[:10]
    
    return render(request, 'movies/admin_dashboard.html', {
        'daily_revenue': daily_revenue,
        'theater_stats': theater_stats,
        'top_movies': top_movies
    })

# --- 5. User Profile ---
@login_required
def booking_history(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'movies/booking_history.html', {'bookings': bookings})