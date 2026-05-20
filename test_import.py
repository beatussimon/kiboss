import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

try:
    from kiboss.apps.notifications.consumers import NotificationConsumer
    from kiboss.apps.messaging.consumers import ChatConsumer
    print("Success: Imported consumers")
except Exception as e:
    print("Error importing consumers:", str(e))
    import traceback
    traceback.print_exc()
