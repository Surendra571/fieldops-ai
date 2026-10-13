from app.core.exceptions import AuthenticationException, ConflictException
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repo import UserRepository
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(self, user_in: UserCreate) -> UserResponse:
        existing = await self.user_repo.get_by_email(user_in.email)
        if existing:
            raise ConflictException(f"A user with email '{user_in.email}' already exists.")

        user_data = user_in.model_dump()
        raw_password = user_data.pop("password")
        user_data["hashed_password"] = hash_password(raw_password)
        user_data["role"] = user_in.role.value

        created = await self.user_repo.create(user_data)
        return UserResponse(**created)

    async def authenticate(self, login_in: UserLogin) -> TokenResponse:
        user_doc = await self.user_repo.get_by_email(login_in.email)
        if not user_doc:
            raise AuthenticationException("Invalid email or password.")

        if not user_doc.get("is_active", True):
            raise AuthenticationException("User account is inactive.")

        if not verify_password(login_in.password, user_doc.get("hashed_password", "")):
            raise AuthenticationException("Invalid email or password.")

        token = create_access_token(
            subject=user_doc["id"],
            role=user_doc["role"],
        )
        return TokenResponse(
            access_token=token,
            user=UserResponse(**user_doc),
        )

    async def get_user_by_id(self, user_id: str) -> UserResponse | None:
        doc = await self.user_repo.get_by_id(user_id)
        if doc:
            return UserResponse(**doc)
        return None
