from django.apps import AppConfig

class UsersConfig(AppConfig): 
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Users'  # <-- This must match your folder name exactly