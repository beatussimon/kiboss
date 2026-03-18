from django.core.management.base import BaseCommand
from kiboss.apps.payments.models import OfflinePaymentMethod

class Command(BaseCommand):
    help = 'Seeds initial Tanzanian payment methods into the database'

    def handle(self, *args, **kwargs):
        payment_methods = [
            {
                'network_name': 'Vodacom M-Pesa',
                'payment_type': 'MOBILE_MONEY',
                'payment_number': '075X XXX XXX (Update in Admin)',
                'account_name': 'KIBOSS LIPA NAMBA',
                'instructions': 'Go to M-Pesa -> Pay by Lipa Namba -> Enter Lipa Namba -> Enter Amount.',
                'lipa_namba': '123456',
                'is_system_wide': True,
                'display_order': 1
            },
            {
                'network_name': 'Tigo Pesa',
                'payment_type': 'MOBILE_MONEY',
                'payment_number': '071X XXX XXX (Update in Admin)',
                'account_name': 'KIBOSS LIPA NAMBA',
                'instructions': 'Go to Tigo Pesa -> Pay Bill -> Enter Lipa Namba.',
                'lipa_namba': '654321',
                'is_system_wide': True,
                'display_order': 2
            },
            {
                'network_name': 'Airtel Money',
                'payment_type': 'MOBILE_MONEY',
                'payment_number': '078X XXX XXX (Update in Admin)',
                'account_name': 'KIBOSS LIPA NAMBA',
                'instructions': 'Go to Airtel Money -> Make Payment.',
                'lipa_namba': '112233',
                'is_system_wide': True,
                'display_order': 3
            },
            {
                'network_name': 'Halo Pesa',
                'payment_type': 'MOBILE_MONEY',
                'payment_number': '062X XXX XXX (Update in Admin)',
                'account_name': 'KIBOSS LIPA NAMBA',
                'instructions': 'Go to Halo Pesa -> Pay Merchant.',
                'lipa_namba': '445566',
                'is_system_wide': True,
                'display_order': 4
            },
            {
                'network_name': 'CRDB Bank',
                'payment_type': 'BANK',
                'payment_number': '015XXXXXXXXXXXXXXXX (Update in Admin)',
                'account_name': 'KIBOSS TECHNOLOGIES',
                'instructions': 'Transfer directly to CRDB Account.',
                'lipa_namba': '',
                'is_system_wide': True,
                'display_order': 5
            },
            {
                'network_name': 'NMB Bank',
                'payment_type': 'BANK',
                'payment_number': '201XXXXXXXXXXXXXXXX (Update in Admin)',
                'account_name': 'KIBOSS TECHNOLOGIES',
                'instructions': 'Transfer directly to NMB Account.',
                'lipa_namba': '',
                'is_system_wide': True,
                'display_order': 6
            }
        ]

        for method_data in payment_methods:
            network_name = method_data.pop('network_name')
            obj, created = OfflinePaymentMethod.objects.get_or_create(
                network_name=network_name,
                is_system_wide=True,
                defaults=method_data
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created payment method: {network_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Payment method already exists: {network_name}'))

        self.stdout.write(self.style.SUCCESS('Finished seeding payment methods.'))
