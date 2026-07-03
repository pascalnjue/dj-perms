"""
Admin configuration for the Django Permissions Demo.

Django Permissions at work:
- The admin site itself uses Django's permission system
- ModelAdmin classes can restrict access via has_*_permission methods
- Showing how the admin ties into the same permission framework
"""

from django.contrib import admin

from .models import Account, Driver, Order, Tenant, UserProfile


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'order_count', 'active_drivers', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'order_count', 'is_active', 'created_at']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name', 'contact_email']


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ['user', 'home_tenant', 'vehicle_type', 'is_active', 'delivery_count']
    list_filter = ['home_tenant', 'is_active']
    search_fields = ['user__username', 'license_number']
    filter_horizontal = ['shared_tenants']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['pk', 'account', 'tenant_name', 'status', 'driver_name', 'amount', 'created_at']
    list_filter = ['status', 'account__tenant']
    search_fields = ['description', 'account__name']
    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description='Tenant')
    def tenant_name(self, obj):
        return obj.account.tenant.name

    @admin.display(description='Driver')
    def driver_name(self, obj):
        return obj.driver.user.username if obj.driver else None


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'tenant', 'created_at']
    list_filter = ['role', 'tenant']
    search_fields = ['user__username']
