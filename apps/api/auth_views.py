"""
API - Authentication Views.

JWT-based authentication for the API layer.
These endpoints handle login, token refresh, and user info retrieval.
"""
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class UserSerializer:
    """Simple user serialization without DRF serializer."""
    
    @staticmethod
    def to_dict(user: CompanyUser) -> dict:
        return {
            "id": user.id,
            "phone": user.phone,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "company_id": user.company_id,
            "company_code": user.company.code if user.company else None,
            "date_joined": user.date_joined.isoformat(),
        }


class LoginAPI(APIView):
    """
    POST: Authenticate user and return JWT tokens.
    
    Request body:
        - phone: User's phone number
        - password: User's password
        - company_code: (optional) Company code for tenant login
    
    Response:
        - user: User details
        - tokens: { access, refresh }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        password = request.data.get("password")
        company_code = request.data.get("company_code")

        if not phone or not password:
            return Response(
                {"error": "Phone and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user
        user = authenticate(request, username=phone, password=password)
        
        if not user:
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"error": "Account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # For tenant login, verify company code matches
        if company_code:
            if user.role == UserRole.PLATFORM_OWNER:
                # Platform owners can log into any company for support
                pass
            elif user.company:
                if user.company.code != company_code:
                    return Response(
                        {"error": "You don't have access to this company."},
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                return Response(
                    {"error": "User is not associated with any company."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "user": UserSerializer.to_dict(user),
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        })


class TokenRefreshAPI(APIView):
    """
    POST: Refresh access token using refresh token.
    
    Request body:
        - refresh: Refresh token
    
    Response:
        - access: New access token
        - refresh: New refresh token (optional rotation)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            })
        except Exception as e:
            return Response(
                {"error": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED
            )


class MeAPI(APIView):
    """
    GET: Return current authenticated user's details.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer.to_dict(request.user))


class LogoutAPI(APIView):
    """
    POST: Blacklist the refresh token (logout).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({"message": "Successfully logged out."})
        except Exception:
            return Response({"message": "Logged out."})


class ChangePasswordAPI(APIView):
    """
    POST: Change user's password.
    
    Request body:
        - current_password: Current password
        - new_password: New password
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not current_password or not new_password:
            return Response(
                {"error": "Current and new passwords are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not request.user.check_password(current_password):
            return Response(
                {"error": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(new_password) < 6:
            return Response(
                {"error": "Password must be at least 6 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.user.set_password(new_password)
        request.user.save()

        return Response({"message": "Password changed successfully."})
