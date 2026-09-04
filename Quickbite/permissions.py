from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Admins only, for any method."""

    message = 'Admin access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)


class IsKitchenOrAdmin(BasePermission):
    """Kitchen staff and admins. Used for order status changes and QR checks."""

    message = 'Only kitchen staff and admins can do this.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and (user.is_kitchen or user.is_admin))


class IsAdminOrReadOnly(BasePermission):
    """
    Anyone may read; only admins may write.

    This is the whole menu app: customers browse it without an account, admins
    maintain it. It replaces the get_permissions() + per-method `if not
    request.user.is_admin` pair that every menu view used to carry.
    """

    message = 'Only admins can change the menu.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)


class IsCustomer(BasePermission):
    """Customers only. Placing an order is not something staff do."""

    message = 'Only customers can place orders.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_customer)
