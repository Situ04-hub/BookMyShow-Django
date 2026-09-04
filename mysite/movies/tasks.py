try:
    from celery import shared_task
except ImportError:
    # Dummy decorator if celery is not installed (e.g. on Vercel)
    def shared_task(func=None, **kwargs):
        if func is None:
            return lambda f: f
        return func
from django.core.mail import EmailMessage
from django.conf import settings
from .models import Booking, SeatReservation
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import qrcode
import io

@shared_task
def generate_and_send_ticket(booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id, payment_status='CONFIRMED')
    except Booking.DoesNotExist:
        return f"Booking {booking_id} not found or not confirmed."

    # Generate QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"Booking ID: {booking.booking_id}\nShow: {booking.show.movie.name}")
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    # Generate PDF in memory
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 24)
    p.drawString(100, 750, "BookMyShow E-Ticket")
    
    p.setFont("Helvetica", 14)
    p.drawString(100, 700, f"Booking ID: {booking.booking_id}")
    p.drawString(100, 675, f"Movie: {booking.show.movie.name}")
    p.drawString(100, 650, f"Theater: {booking.show.screen.theater.name}")
    p.drawString(100, 625, f"Screen: {booking.show.screen.name}")
    p.drawString(100, 600, f"Time: {booking.show.start_time.strftime('%Y-%m-%d %H:%M')}")
    
    seats = ", ".join([res.seat.seat_number for res in booking.reserved_seats.all()])
    p.drawString(100, 575, f"Seats: {seats}")
    p.drawString(100, 550, f"Total Amount: ${booking.total_amount}")
    
    # Add QR code to PDF
    qr_buffer = io.BytesIO()
    img.save(qr_buffer, format='PNG')
    from reportlab.lib.utils import ImageReader
    p.drawImage(ImageReader(qr_buffer), 400, 600, width=1.5*inch, height=1.5*inch)
    
    p.showPage()
    p.save()
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    # Send Email
    subject = f"Your Tickets for {booking.show.movie.name}"
    message = f"Hi {booking.user.username},\n\nYour booking is confirmed! Attached is your E-Ticket.\n\nEnjoy the movie!"
    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@bookmyshowclone.com',
        [booking.user.email]
    )
    email.attach(f"ticket_{booking.booking_id}.pdf", pdf_bytes, 'application/pdf')
    email.send(fail_silently=False)
    
    return f"Ticket sent successfully to {booking.user.email}"

@shared_task
def release_expired_reservations():
    # Releases seats that have been reserved for more than 2 minutes without payment completion
    expiration_time = timezone.now() - timezone.timedelta(minutes=2)
    expired_reservations = SeatReservation.objects.filter(
        status='RESERVED',
        reserved_at__lt=expiration_time,
        booking__payment_status='PENDING' # Only pending bookings
    )
    
    count = expired_reservations.count()
    if count > 0:
        # We also need to mark the associated bookings as failed/cancelled
        booking_ids = expired_reservations.values_list('booking_id', flat=True)
        Booking.objects.filter(id__in=booking_ids, payment_status='PENDING').update(payment_status='CANCELLED')
        
        expired_reservations.update(status='AVAILABLE', user=None, booking=None, reserved_at=None)
        
    return f"Released {count} expired seat reservations."
