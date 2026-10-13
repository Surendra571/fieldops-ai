from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_current_user
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Access"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new user account (role defaults to CUSTOMER unless specified by ADMIN)."""
    return await auth_service.register(user_in)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login_user(
    login_in: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Authenticate with email and password to receive a JWT access token."""
    return await auth_service.authenticate(login_in)


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_authenticated_user_profile(
    current_user: UserResponse = Depends(get_current_user),
):
    """Retrieve profile of currently authenticated user."""
    return current_user
