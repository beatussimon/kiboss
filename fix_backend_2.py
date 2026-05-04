import re

with open("kiboss/apps/assets/views.py", "r") as f:
    content = f.read()

# AssetViewSet filter
if "is_listed=True" not in content:
    asset_filter = """        
        # Filter by owner
        owner = self.request.query_params.get('owner')
        if owner == 'me':
            queryset = queryset.filter(owner=self.request.user)
        elif owner:
            queryset = queryset.filter(owner_id=owner)
        else:
            # Public listing filters [BE-03]
            queryset = queryset.filter(is_listed=True).exclude(verification_status='REJECTED')"""
            
    content = re.sub(
        r"        # Filter by owner\n        owner = self\.request\.query_params\.get\('owner'\)\n        if owner == 'me':\n            queryset = queryset\.filter\(owner=self\.request\.user\)\n        elif owner:\n            queryset = queryset\.filter\(owner_id=owner\)",
        asset_filter,
        content
    )
    with open("kiboss/apps/assets/views.py", "w") as f:
        f.write(content)


with open("kiboss/apps/rides/views.py", "r") as f:
    content = f.read()

if "departure_time__gte=timezone.now()" not in content:
    ride_filter = """        if status_param:
            queryset = queryset.filter(status=status_param)
        elif not is_own_rides:
            # Apply default filter if no specific filters provided
            queryset = queryset.filter(
                status__in=[RideStatus.OPEN, RideStatus.SCHEDULED],
                departure_time__gte=timezone.now()
            )"""
            
    content = re.sub(
        r"        if status_param:\n            queryset = queryset\.filter\(status=status_param\)\n        elif not is_own_rides:\n            # \[T3-04\] Apply default filter if no specific filters provided\n            queryset = queryset\.filter\(status__in=\[RideStatus\.OPEN, RideStatus\.SCHEDULED\]\)",
        ride_filter,
        content
    )
    with open("kiboss/apps/rides/views.py", "w") as f:
        f.write(content)

with open("kiboss/apps/users/views.py", "r") as f:
    content = f.read()

if "change_password" not in content:
    pw_action = """
    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        user = request.user
        if not user.check_password(request.data.get('current_password', '')):
            from rest_framework.response import Response
            return Response({'error': 'Current password is incorrect'}, status=400)
        user.set_password(request.data['new_password'])
        user.save()
        from rest_framework.response import Response
        return Response({'status': 'password changed'})
"""
    # Insert it inside UserViewSet
    if "class UserViewSet(viewsets.ModelViewSet):" in content:
        content = content.replace("class UserViewSet(viewsets.ModelViewSet):", "class UserViewSet(viewsets.ModelViewSet):\n" + pw_action)
        with open("kiboss/apps/users/views.py", "w") as f:
            f.write(content)

print("Backend Views Fixed")
