from kiboss.apps.rbac.models import Role, Permission, RolePermission

# Clear existing if any (should be empty anyway based on our check)
# RolePermission.objects.all().delete()

# 1. VERIFIER Permissions (General)
verifier_perms = [
    Permission.USER_VIEW,
    Permission.ASSET_VIEW,
    Permission.ASSET_VERIFY,
    Permission.USER_VERIFY,
    Permission.ASSET_REJECT,
]
for perm in verifier_perms:
    RolePermission.objects.get_or_create(role=Role.VERIFIER, permission=perm)

# 1a. CAR_VERIFIER Permissions
car_verifier_perms = [
    Permission.ASSET_VIEW,
    Permission.ASSET_VERIFY,
    Permission.ASSET_REJECT,
]
for perm in car_verifier_perms:
    RolePermission.objects.get_or_create(role=Role.CAR_VERIFIER, permission=perm)

# 1b. RIDE_BUSINESS_VERIFIER Permissions
business_verifier_perms = [
    Permission.USER_VIEW,
    Permission.USER_VERIFY,
]
for perm in business_verifier_perms:
    RolePermission.objects.get_or_create(role=Role.RIDE_BUSINESS_VERIFIER, permission=perm)

# 2. SUPPORT Permissions
support_perms = [
    Permission.USER_VIEW,
    Permission.BOOKING_VIEW,
    Permission.DISPUTE_VIEW,
    Permission.DISPUTE_RESOLVE,
    Permission.MESSAGE_VIEW,
    Permission.SUPPORT_TICKET,
]
for perm in support_perms:
    RolePermission.objects.get_or_create(role=Role.SUPPORT, permission=perm)

# 3. OPS Permissions
ops_perms = [
    Permission.USER_VIEW,
    Permission.USER_VERIFY,
    Permission.ASSET_VIEW,
    Permission.ASSET_VERIFY,
    Permission.BOOKING_VIEW,
    Permission.AUDIT_VIEW,
]
for perm in ops_perms:
    RolePermission.objects.get_or_create(role=Role.OPS, permission=perm)

# 4. SUPER_ADMIN Permissions (Everything)
for perm in Permission:
    RolePermission.objects.get_or_create(role=Role.SUPER_ADMIN, permission=perm)

print("RBAC Seeding Complete.")
