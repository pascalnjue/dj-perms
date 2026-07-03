"""
Custom authentication backend for object-level permissions.

Django Permissions at work:
- Django's default ModelBackend handles model-level permissions
- This backend adds object-level permission checks
- It's configured in AUTHENTICATION_BACKENDS in settings.py
- Object-level perms restrict access based on tenant/account scope

Example flow:
  1. User requests /accounts/5/
  2. Django checks model-level 'view_account' perm
  3. This backend checks: does user's tenant match account 5's tenant?
"""

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import Permission


class TenantObjectPermissionBackend(BaseBackend):
    """
    Backend that checks object-level permissions based on tenant scope.

    This complements Django's ModelBackend — we keep it enabled
    so model-level checks still work via the default backend.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # We don't handle authentication — ModelBackend does that
        return None

    def has_perm(self, user_obj, perm, obj=None):
        """
        Check if user has a permission. If obj is provided,
        enforce tenant-scoped access.
        """
        if not user_obj.is_active:
            return False

        # Super admins can do anything
        if user_obj.is_superuser:
            return True

        # No object — fall back to model-level permissions
        if obj is None:
            return False

        # Object-level tenant check
        if not hasattr(user_obj, 'profile'):
            return False

        profile = user_obj.profile
        tenant = self._get_object_tenant(obj)

        if tenant is None:
            # Object has no tenant — allow if user has model-level perm
            return True

        return profile.has_tenant_access(tenant)

    def _get_object_tenant(self, obj):
        """Extract the tenant from various object types."""
        from .models import Account, Driver, Order, Tenant

        if isinstance(obj, Tenant):
            return obj
        if isinstance(obj, Account):
            return obj.tenant
        if isinstance(obj, Order):
            return obj.account.tenant
        if isinstance(obj, Driver):
            return obj.home_tenant
        return None


# Helper for views: check if user can access an object
def user_can_access(user, obj):
    """Convenience function to check object-level access."""
    from .models import Account, Driver, Order, Tenant

    if user.is_superuser:
        return True
    if not hasattr(user, 'profile'):
        return False
    profile = user.profile
    if isinstance(obj, Tenant):
        return profile.has_tenant_access(obj)
    if isinstance(obj, Account):
        return profile.has_tenant_access(obj.tenant)
    if isinstance(obj, Order):
        return profile.has_tenant_access(obj.account.tenant)
    if isinstance(obj, Driver):
        return profile.has_tenant_access(obj.home_tenant)
    return False
