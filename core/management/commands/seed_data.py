"""
Management command to seed the database with demo data.

Usage:
    python manage.py seed_data

Creates:
    - 3 Tenants (Nairobi Express, Mombasa Logistics, Kisumu Couriers)
    - 6 Accounts (2 per tenant)
    - 5 Drivers (with cross-tenant sharing)
    - 6 Users with different roles
    - 20+ Orders with various statuses

All users have password: demo1234
"""

from datetime import timedelta

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Account, Driver, Order, Tenant, UserProfile
from core.signals import ensure_role_groups


class Command(BaseCommand):
    help = 'Seed the database with demo data for the Django Permissions Demo'

    def handle(self, *args, **options):
        self.stdout.write('🌱 Seeding database...\n')

        # Clear existing data
        self.stdout.write('  Clearing existing data...')
        Order.objects.all().delete()
        Driver.objects.all().delete()
        Account.objects.all().delete()
        UserProfile.objects.all().delete()
        # Keep superuser, delete other users
        User.objects.filter(is_superuser=False).delete()
        # Keep tenant groups, delete others
        Group.objects.exclude(name__startswith='tenant_').exclude(name__startswith='role_').delete()
        Tenant.objects.all().delete()
        self.stdout.write('  ✅ Cleared.\n')

        # Ensure standard role groups exist
        ensure_role_groups()

        # ── Create Tenants ──────────────────────────────────────────
        self.stdout.write('  Creating tenants...')
        tenants = {
            'nex': Tenant.objects.create(
                name='Nairobi Express', slug='nairobi-express', is_active=True
            ),
            'mls': Tenant.objects.create(
                name='Mombasa Logistics', slug='mombasa-logistics', is_active=True
            ),
            'ksm': Tenant.objects.create(
                name='Kisumu Couriers', slug='kisumu-couriers', is_active=True
            ),
        }
        self.stdout.write(f'  ✅ {len(tenants)} tenants (with auto-created Groups).')

        # ── Create Accounts ─────────────────────────────────────────
        self.stdout.write('  Creating accounts...')
        accounts_data = [
            # Nairobi Express accounts
            {'tenant': 'nex', 'name': 'Java House', 'email': 'orders@javahouse.co.ke'},
            {'tenant': 'nex', 'name': 'Naivas Supermarket', 'email': 'delivery@naivas.co.ke'},
            # Mombasa Logistics accounts
            {'tenant': 'mls', 'name': 'Diani Reef Hotel', 'email': 'supply@dianireef.com'},
            {'tenant': 'mls', 'name': 'Coast General Supplies', 'email': 'info@coastgeneral.co.ke'},
            # Kisumu Couriers accounts
            {'tenant': 'ksm', 'name': 'Kiboko Bay Resort', 'email': 'orders@kibokobay.com'},
            {'tenant': 'ksm', 'name': 'Lake View Distributors', 'email': 'sales@lakeview.co.ke'},
        ]
        accounts = {}
        for ad in accounts_data:
            accounts[ad['name']] = Account.objects.create(
                tenant=tenants[ad['tenant']],
                name=ad['name'],
                contact_email=ad['email'],
            )
        self.stdout.write(f'  ✅ {len(accounts)} accounts.')

        # ── Create Users ────────────────────────────────────────────
        self.stdout.write('  Creating users...')
        users = {}

        # Super Admin
        users['admin'] = User.objects.create_superuser(
            'admin', 'admin@demo.com', 'demo1234',
            first_name='System', last_name='Admin'
        )
        profile = UserProfile.objects.create(user=users['admin'], role='super_admin')
        # Super admin gets all tenant groups
        for tenant in Tenant.objects.all():
            if tenant.group:
                users['admin'].groups.add(tenant.group)

        # Tenant Admins
        users['nex_admin'] = User.objects.create_user(
            'nex_admin', 'nex@demo.com', 'demo1234',
            first_name='Nairobi', last_name='Admin'
        )
        UserProfile.objects.create(user=users['nex_admin'], role='tenant_admin', tenant=tenants['nex'])

        users['mls_admin'] = User.objects.create_user(
            'mls_admin', 'mls@demo.com', 'demo1234',
            first_name='Mombasa', last_name='Admin'
        )
        UserProfile.objects.create(user=users['mls_admin'], role='tenant_admin', tenant=tenants['mls'])

        # Account Managers
        users['java_manager'] = User.objects.create_user(
            'java_manager', 'java@demo.com', 'demo1234',
            first_name='Java', last_name='Manager'
        )
        profile = UserProfile.objects.create(
            user=users['java_manager'], role='account_manager', tenant=tenants['nex']
        )
        profile.managed_accounts.add(accounts['Java House'])

        users['naivas_manager'] = User.objects.create_user(
            'naivas_manager', 'naivas@demo.com', 'demo1234',
            first_name='Naivas', last_name='Manager'
        )
        profile = UserProfile.objects.create(
            user=users['naivas_manager'], role='account_manager', tenant=tenants['nex']
        )
        profile.managed_accounts.add(accounts['Naivas Supermarket'])

        self.stdout.write(f'  ✅ {len(users)} users ({", ".join(users.keys())}).')

        # ── Create Drivers ──────────────────────────────────────────
        self.stdout.write('  Creating drivers...')
        driver_users = {
            'mike': User.objects.create_user('mike_rider', 'mike@demo.com', 'demo1234'),
            'sarah': User.objects.create_user('sarah_rider', 'sarah@demo.com', 'demo1234'),
            'john': User.objects.create_user('john_rider', 'john@demo.com', 'demo1234'),
            'aminata': User.objects.create_user('aminata_rider', 'aminata@demo.com', 'demo1234'),
            'david': User.objects.create_user('david_rider', 'david@demo.com', 'demo1234'),
        }

        drivers = {}
        drivers['mike'] = Driver.objects.create(
            user=driver_users['mike'], home_tenant=tenants['nex'],
            vehicle_type='Motorcycle', license_number='NBI-1234', phone='+254700111222'
        )
        UserProfile.objects.create(user=driver_users['mike'], role='driver', tenant=tenants['nex'])

        drivers['sarah'] = Driver.objects.create(
            user=driver_users['sarah'], home_tenant=tenants['nex'],
            vehicle_type='Van', license_number='NBI-5678', phone='+254700333444'
        )
        UserProfile.objects.create(user=driver_users['sarah'], role='driver', tenant=tenants['nex'])
        # Sarah is shared with Mombasa
        drivers['sarah'].shared_tenants.add(tenants['mls'])

        drivers['john'] = Driver.objects.create(
            user=driver_users['john'], home_tenant=tenants['mls'],
            vehicle_type='Truck', license_number='MSA-9012', phone='+254711555666'
        )
        UserProfile.objects.create(user=driver_users['john'], role='driver', tenant=tenants['mls'])
        # John is shared with both other tenants
        drivers['john'].shared_tenants.add(tenants['nex'], tenants['ksm'])

        drivers['aminata'] = Driver.objects.create(
            user=driver_users['aminata'], home_tenant=tenants['mls'],
            vehicle_type='Motorcycle', license_number='MSA-3456', phone='+254722777888'
        )
        UserProfile.objects.create(user=driver_users['aminata'], role='driver', tenant=tenants['mls'])

        drivers['david'] = Driver.objects.create(
            user=driver_users['david'], home_tenant=tenants['ksm'],
            vehicle_type='Van', license_number='KSM-7890', phone='+254733999000'
        )
        UserProfile.objects.create(user=driver_users['david'], role='driver', tenant=tenants['ksm'])
        # David is shared with Nairobi
        drivers['david'].shared_tenants.add(tenants['nex'])

        self.stdout.write(f'  ✅ {len(drivers)} drivers with cross-tenant sharing.')

        # ── Create Orders ───────────────────────────────────────────
        self.stdout.write('  Creating orders...')
        now = timezone.now()

        orders_data = [
            # Nairobi Express — Java House
            {'account': 'Java House', 'driver': 'mike', 'status': 'delivered',
             'desc': 'Coffee beans & pastries — daily supply', 'pickup': 'Java House Roastery, Westlands',
             'delivery': 'Java House Gigiri', 'amount': 4500, 'days_ago': 5},
            {'account': 'Java House', 'driver': 'sarah', 'status': 'delivered',
             'desc': 'Catering equipment for corporate event', 'pickup': 'Java House HQ, Kilimani',
             'delivery': 'KICC Conference Center', 'amount': 12500, 'days_ago': 3},
            {'account': 'Java House', 'driver': 'mike', 'status': 'in_transit',
             'desc': 'Takeaway packaging materials', 'pickup': 'Industrial Area Warehouse',
             'delivery': 'Java House Junction', 'amount': 3200, 'days_ago': 0},

            # Nairobi Express — Naivas
            {'account': 'Naivas Supermarket', 'driver': 'sarah', 'status': 'delivered',
             'desc': 'Fresh produce — vegetables & fruits', 'pickup': 'Naivas DC, Mombasa Road',
             'delivery': 'Naivas Karen', 'amount': 8750, 'days_ago': 4},
            {'account': 'Naivas Supermarket', 'driver': 'john', 'status': 'delivered',
             'desc': 'Dairy products restock', 'pickup': 'Brookside Dairy, Ruiru',
             'delivery': 'Naivas Westgate', 'amount': 6200, 'days_ago': 2},
            {'account': 'Naivas Supermarket', 'driver': 'david', 'status': 'picked_up',
             'desc': 'Bakery supplies — flour & yeast', 'pickup': 'Unga House, Industrial Area',
             'delivery': 'Naivas Galleria', 'amount': 3900, 'days_ago': 1},

            # Mombasa Logistics — Diani Reef
            {'account': 'Diani Reef Hotel', 'driver': 'john', 'status': 'delivered',
             'desc': 'Fresh seafood — prawns & lobster', 'pickup': 'Mombasa Old Port',
             'delivery': 'Diani Reef Hotel, South Coast', 'amount': 15000, 'days_ago': 6},
            {'account': 'Diani Reef Hotel', 'driver': 'aminata', 'status': 'delivered',
             'desc': 'Linen & towels for resort', 'pickup': 'Mombasa Textile Market',
             'delivery': 'Diani Reef Hotel', 'amount': 7800, 'days_ago': 3},
            {'account': 'Diani Reef Hotel', 'driver': 'john', 'status': 'confirmed',
             'desc': 'Pool chemicals & maintenance supplies', 'pickup': 'Coast Hardware, Nyali',
             'delivery': 'Diani Reef Hotel', 'amount': 11200, 'days_ago': 0},

            # Mombasa Logistics — Coast General
            {'account': 'Coast General Supplies', 'driver': 'aminata', 'status': 'delivered',
             'desc': 'Construction materials — cement & steel', 'pickup': 'Bamburi Cement Factory',
             'delivery': 'Likoni Construction Site', 'amount': 22000, 'days_ago': 5},
            {'account': 'Coast General Supplies', 'driver': 'sarah', 'status': 'in_transit',
             'desc': 'Office furniture delivery', 'pickup': 'Furniture Palace, Mombasa Rd',
             'delivery': 'Coast General HQ, Mombasa CBD', 'amount': 18500, 'days_ago': 1},
            {'account': 'Coast General Supplies', 'driver': 'aminata', 'status': 'pending',
             'desc': 'Cleaning supplies bulk order', 'pickup': 'Coast Distributors, Changamwe',
             'delivery': 'Coast General Warehouse', 'amount': 4500, 'days_ago': 0},

            # Kisumu Couriers — Kiboko Bay
            {'account': 'Kiboko Bay Resort', 'driver': 'david', 'status': 'delivered',
             'desc': 'Fresh tilapia — Lake Victoria catch', 'pickup': 'Kisumu Fish Market',
             'delivery': 'Kiboko Bay Resort, Dunga Beach', 'amount': 6800, 'days_ago': 4},
            {'account': 'Kiboko Bay Resort', 'driver': 'david', 'status': 'delivered',
             'desc': 'Bar supplies — drinks & glassware', 'pickup': 'Kisumu Wholesalers, Oginga Odinga Rd',
             'delivery': 'Kiboko Bay Resort', 'amount': 9500, 'days_ago': 2},
            {'account': 'Kiboko Bay Resort', 'driver': 'david', 'status': 'pending',
             'desc': 'Solar panel equipment', 'pickup': 'Lake Basin Mall, Kisumu',
             'delivery': 'Kiboko Bay Resort', 'amount': 35000, 'days_ago': 0},

            # Kisumu Couriers — Lake View
            {'account': 'Lake View Distributors', 'driver': 'john', 'status': 'delivered',
             'desc': 'Farm equipment — irrigation pipes', 'pickup': 'Agrovet Center, Kisumu',
             'delivery': 'Lake View Farm, Ahero', 'amount': 14200, 'days_ago': 5},
            {'account': 'Lake View Distributors', 'driver': 'david', 'status': 'confirmed',
             'desc': 'Packaged foods for retail', 'pickup': 'Kisumu Industrial Park',
             'delivery': 'Lake View Outlet, Kondele', 'amount': 5600, 'days_ago': 1},
            {'account': 'Lake View Distributors', 'driver': 'david', 'status': 'pending',
             'desc': 'Fertilizer & seeds — planting season', 'pickup': 'Kenya Seed Company, Kitale',
             'delivery': 'Lake View Farm, Ahero', 'amount': 28000, 'days_ago': 0},

            # Cross-tenant deliveries
            {'account': 'Java House', 'driver': 'john', 'status': 'pending',
             'desc': '[CROSS-TENANT] Specialty coffee from Mombasa port',
             'pickup': 'Mombasa Container Terminal',
             'delivery': 'Java House Roastery, Nairobi', 'amount': 45000, 'days_ago': 0},
            {'account': 'Naivas Supermarket', 'driver': 'john', 'status': 'cancelled',
             'desc': '[CROSS-TENANT] Imported wines — order cancelled',
             'pickup': 'Mombasa Bonded Warehouse',
             'delivery': 'Naivas Supermarket, Nairobi', 'amount': 32000, 'days_ago': 1},
        ]

        for od in orders_data:
            days = od['days_ago']
            created = now - timedelta(days=days, hours=days * 3)
            delivered_at = None
            if od['status'] == 'delivered':
                delivered_at = created + timedelta(hours=4 + days)

            Order.objects.create(
                account=accounts[od['account']],
                driver=drivers[od['driver']],
                description=od['desc'],
                pickup_address=od['pickup'],
                delivery_address=od['delivery'],
                status=od['status'],
                amount=od['amount'],
                created_at=created,
                updated_at=created + timedelta(hours=1),
                delivered_at=delivered_at,
            )

        self.stdout.write(f'  ✅ {len(orders_data)} orders (including cross-tenant deliveries).')

        self.stdout.write('\n🎉 Seed complete!')
        self.stdout.write('─' * 50)
        self.stdout.write('Demo Users (all with password: demo1234):')
        self.stdout.write('')
        self.stdout.write('  👑 admin          — Super Admin (sees everything)')
        self.stdout.write('  🏢 nex_admin      — Tenant Admin (Nairobi Express)')
        self.stdout.write('  🏢 mls_admin      — Tenant Admin (Mombasa Logistics)')
        self.stdout.write('  👤 java_manager   — Account Manager (Java House)')
        self.stdout.write('  👤 naivas_manager  — Account Manager (Naivas)')
        self.stdout.write('  🛵 mike_rider     — Driver (Nairobi Express, motorcycle)')
        self.stdout.write('  🛵 sarah_rider    — Driver (Nairobi + Mombasa, van)')
        self.stdout.write('  🛵 john_rider     — Driver (Mombasa + shared to all, truck)')
        self.stdout.write('  🛵 aminata_rider  — Driver (Mombasa, motorcycle)')
        self.stdout.write('  🛵 david_rider    — Driver (Kisumu + shared to Nairobi, van)')
        self.stdout.write('')
        self.stdout.write('Run: python manage.py runserver')
        self.stdout.write('─' * 50)
