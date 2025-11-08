import os
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

# Set the settings module for Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cloud_storage.settings")

# Initialize Django
application = get_wsgi_application()

# Run migrations
call_command("migrate")

print("✅ Database setup completed successfully!")
