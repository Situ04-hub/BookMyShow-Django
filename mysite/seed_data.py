import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from movies.models import City, Theater, Screen, Seat, Movie, Show
from django.contrib.auth.models import User

def seed_data():
    print("Clearing old data...")
    City.objects.all().delete()
    Movie.objects.all().delete()
    # User.objects.exclude(is_superuser=True).delete()

    print("Creating Demo Data...")

    # Create User
    if not User.objects.filter(username='demouser').exists():
        user = User.objects.create_user('demouser', 'demo@example.com', 'password123')
    else:
        user = User.objects.get(username='demouser')

    # Create Cities
    bhubaneswar = City.objects.create(name="Bhubaneswar")
    cuttack = City.objects.create(name="Cuttack")

    # Create Theaters
    inox = Theater.objects.create(name="INOX: Symphony Mall", city=bhubaneswar, address="Symphony Mall, Bhubaneswar")
    pvr = Theater.objects.create(name="INOX: SGBL Square Mall", city=cuttack, address="SGBL Square Mall, Cuttack")

    # Create Screens
    inox_s1 = Screen.objects.create(name="Screen 1 (IMAX)", theater=inox)
    pvr_s1 = Screen.objects.create(name="Audi 1", theater=pvr)

    # Create Seats for INOX Screen 1
    seats_to_create = []
    for row in ['A', 'B', 'C', 'D']:
        for num in range(1, 11):
            seats_to_create.append(Seat(
                screen=inox_s1,
                seat_number=f"{row}{num}",
                row=row,
                seat_type="Premium" if row in ['C', 'D'] else "Standard"
            ))
    
    # Create Seats for PVR Audi 1
    for row in ['A', 'B', 'C']:
        for num in range(1, 11):
            seats_to_create.append(Seat(
                screen=pvr_s1,
                seat_number=f"{row}{num}",
                row=row,
                seat_type="Premium" if row == 'C' else "Standard"
            ))
            
    Seat.objects.bulk_create(seats_to_create)

    # Create Movies
    avengers = Movie.objects.create(
        name="Avengers: Secret Wars",
        genre="Action, Sci-Fi",
        language="English",
        release_date=timezone.now().date(),
        duration=180,
        age_certification="UA",
        youtube_trailer_url="https://www.youtube.com/embed/eOrNdBpGMv8",
        popularity_score=100,
        average_rating=4.8,
        cast="Robert Downey Jr, Tom Holland, Benedict Cumberbatch",
        description="The ultimate crossover event in the Marvel Cinematic Universe."
    )

    jawan = Movie.objects.create(
        name="Jawan 2",
        genre="Action, Thriller",
        language="Hindi",
        release_date=timezone.now().date() + timedelta(days=1),
        duration=165,
        age_certification="UA",
        youtube_trailer_url="https://www.youtube.com/embed/MWOtxptmCEI",
        popularity_score=95,
        average_rating=4.5,
        cast="Shah Rukh Khan, Nayanthara, Vijay Sethupathi",
        description="A high-octane action thriller."
    )
    
    inception = Movie.objects.create(
        name="Inception (Re-release)",
        genre="Sci-Fi, Thriller",
        language="English",
        release_date=timezone.now().date() - timedelta(days=5),
        duration=148,
        age_certification="UA",
        youtube_trailer_url="https://www.youtube.com/embed/YoHD9XEInc0",
        popularity_score=88,
        average_rating=4.9,
        cast="Leonardo DiCaprio, Joseph Gordon-Levitt",
        description="A thief who steals corporate secrets through the use of dream-sharing technology."
    )

    # Create Shows
    now = timezone.now()
    
    # Shows for INOX Mumbai
    Show.objects.create(
        movie=avengers,
        screen=inox_s1,
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=5),
        ticket_price=15.00
    )
    Show.objects.create(
        movie=avengers,
        screen=inox_s1,
        start_time=now + timedelta(hours=6),
        end_time=now + timedelta(hours=9),
        ticket_price=18.00
    )
    Show.objects.create(
        movie=inception,
        screen=inox_s1,
        start_time=now + timedelta(hours=10),
        end_time=now + timedelta(hours=12, minutes=30),
        ticket_price=12.00
    )

    # Shows for PVR Delhi
    Show.objects.create(
        movie=jawan,
        screen=pvr_s1,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=3, minutes=45),
        ticket_price=10.00
    )
    Show.objects.create(
        movie=avengers,
        screen=pvr_s1,
        start_time=now + timedelta(hours=4),
        end_time=now + timedelta(hours=7),
        ticket_price=14.00
    )

    print("Successfully seeded database with demo data!")

if __name__ == '__main__':
    seed_data()
