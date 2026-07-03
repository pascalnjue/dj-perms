# DJ Perms — Interactive Django Permissions Demo

A living, clickable demo of Django's authentication and authorization system
built around a multi-tenant delivery platform. Every page annotates which Django
permission mechanism is at work so you can see the framework in action.

## Quick Start

```bash
git clone <repo-url> dj-perms && cd dj-perms
uv sync                          # or pip install django>=6.0
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open **http://localhost:8765** — login as any demo user (password: `demo1234`).

## Demo Users

| User | Role | Scope |
|---|---|---|
| `admin` | Super Admin | Everything — all tenants, permission matrix |
| `nex_admin` | Tenant Admin | Nairobi Express only |
| `mls_admin` | Tenant Admin | Mombasa Logistics only |
| `java_manager` | Account Manager | Java House + Naivas (Nairobi Express) |
| `naivas_manager` | Account Manager | Naivas Supermarket (Nairobi Express) |
| `mike_rider` | Driver (NEX) | Nairobi Express deliveries |
| `sarah_rider` | Driver (NEX + MLS) | Cross-tenant: Nairobi & Mombasa |
| `john_rider` | Driver (all 3) | Shared across every tenant |
| `aminata_rider` | Driver (MLS) | Mombasa only — blocked from Nairobi |
| `david_rider` | Driver (KSM + NEX) | Kisumu + Nairobi |

## What's Inside

### Domain Models

| Model | Key Relationships |
|---|---|
| **Tenant** | Business using the platform. Gets its own Django Group via `post_save` signal. |
| **Account** | Customer account. Strict FK to one Tenant. |
| **Driver** | Delivery personnel. Home tenant + `ManyToMany` shared tenants for cross-tenant work. |
| **Order** | Placed by an Account, delivered by a Driver. Full status lifecycle. |
| **UserProfile** | Extends Django's `User` with role and tenant affiliation (not a custom User model). |

### Permission Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Django Auth                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │   User   │  │  Group   │  │   Permission     │  │
│  │          │──│ (tenant_ │──│  manage_tenant    │  │
│  │  profile │  │  nexus)  │  │  create_order_... │  │
│  └──────────┘  └──────────┘  │  update_delivery_ │  │
│                              └──────────────────┘  │
│  ┌──────────────────────────────────────────────┐   │
│  │  TenantObjectPermissionBackend (custom)       │   │
│  │  → Object-level: "can THIS user see THIS      │   │
│  │    tenant's orders?"                          │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  Signals (auto-setup)                         │   │
│  │  → post_save Tenant → create Django Group     │   │
│  │  → post_save UserProfile → assign groups      │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Three layers of permission checks:**

1. **Model-level** — Django's built-in `ModelBackend` checks `auth_permission` table
2. **Object-level** — `TenantObjectPermissionBackend` checks tenant scope per object
3. **View-level** — `user_can_access()` and `get_user_scope()` filter querysets

### Permission Annotations in the UI

Every page shows coloured badges explaining what Django mechanism is active:

| Badge | Meaning |
|---|---|
| 🔴 `@permission_required` | View decorator checking a model permission |
| 🟣 `object-level` | Custom tenant-scoped access check |
| 🔵 `Django Group` | Permission inherited via group membership |
| 🟢 `model perm` | Django content-type permission |

### Pages

| URL | View | Access Control |
|---|---|---|
| `/` | Dashboard + analytics | `@login_required` — data scoped to user's tenants |
| `/tenants/` | Tenant list | Filtered by `get_user_scope()` |
| `/tenants/<slug>/` | Tenant detail | `user_can_access()` object-level check |
| `/accounts/` | Account list | Scoped to accessible tenants |
| `/accounts/<pk>/` | Account detail | `user_can_access()` per account |
| `/drivers/` | Driver list | Cross-tenant M2M filtering |
| `/drivers/<pk>/` | Driver detail | `user_can_access()` per driver |
| `/orders/` | Order list | Tenant-scoped queryset |
| `/orders/create/` | New order | Account dropdown scoped to user's tenants |
| `/orders/<pk>/` | Order detail | `user_can_access()` + `update_delivery_status` check |
| `/permissions/` | Permission matrix | `@user_passes_test(is_superuser)` only |

### Seed Data

`python manage.py seed_data` creates:

- 3 tenants (Nairobi Express, Mombasa Logistics, Kisumu Couriers)
- 6 accounts (2 per tenant, e.g. Java House, Naivas, Diani Reef Hotel)
- 5 drivers with cross-tenant sharing
- 10 users spanning all 4 roles
- 20 orders across all statuses, including cross-tenant deliveries
- Auto-created Django Groups for every tenant + role

## Project Structure

```
dj-perms/
├── dj_perms/              # Django project config
│   ├── settings.py        # Auth backends, CSRF, installed apps
│   └── urls.py            # Root URL conf → core.urls
├── core/                  # Main application
│   ├── models.py          # Tenant, Account, Driver, Order, UserProfile
│   ├── views.py           # All views with permission annotations
│   ├── urls.py            # App URL patterns
│   ├── auth_backend.py    # Custom object-level permission backend
│   ├── signals.py         # Auto-create groups on tenant/user save
│   ├── admin.py           # Admin site configuration
│   ├── templatetags/      # Custom template filters
│   ├── management/
│   │   └── commands/
│   │       └── seed_data.py   # Demo data seeder
│   └── migrations/
├── templates/
│   ├── base.html          # Layout, nav, Tailwind CDN
│   └── core/
│       ├── dashboard.html
│       ├── login.html
│       ├── tenant_list.html / tenant_detail.html
│       ├── account_list.html / account_detail.html
│       ├── driver_list.html / driver_detail.html
│       ├── order_list.html / order_detail.html / order_create.html
│       └── permission_management.html
├── manage.py
└── pyproject.toml
```

## Tech Stack

- **Django 6.0** with SQLite
- **Tailwind CSS** (CDN, dark theme)
- Python 3.13+
- `uv` for package management

## License

MIT — use this to teach, demo, or build upon.
