import base64
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import (
    get_agent_service,
    get_conversation_repo,
    get_current_user_optional,
    get_customer_repo,
)
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.customer_repo import CustomerRepository
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentVoiceRequest,
    AgentVoiceResponse,
    ConversationSessionRead,
)
from app.schemas.user import UserResponse, UserRole
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["AI Voice & Chat Intake Agent"])


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Multi-turn text conversation with service intake agent",
)
async def chat_interaction(
    payload: AgentChatRequest,
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentChatResponse:
    """
    Submit a customer message in a conversation session.
    Extracts draft fields, invokes safe backend tools, and returns conversational response.
    """
    try:
        token = payload.session_token or x_session_token
        return await agent_service.process_chat(
            session_id=payload.session_id,
            customer_id=payload.customer_id,
            user_message=payload.message,
            session_token=token,
        )
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error in agent chat endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request. Please try again or ask for a representative.",
        ) from e


@router.post(
    "/voice",
    response_model=AgentVoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Audio speech-to-speech interaction with service intake agent",
)
async def voice_interaction(
    payload: AgentVoiceRequest,
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentVoiceResponse:
    """
    Submit base64-encoded audio bytes from customer.
    Transcribes audio (STT), reasons/invokes backend tools, synthesizes speech (TTS), and returns audio response.
    """
    try:
        try:
            audio_bytes = base64.b64decode(payload.audio_base64)
        except Exception as e:
            raise ValidationException("Invalid base64 encoding for audio payload.") from e

        if not audio_bytes:
            raise ValidationException("Empty audio payload received.")

        token = payload.session_token or x_session_token
        return await agent_service.process_voice(
            session_id=payload.session_id,
            customer_id=payload.customer_id,
            audio_content=audio_bytes,
            audio_format=payload.audio_format,
            session_token=token,
        )
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error in agent voice endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing audio. Please try again or ask for a representative.",
        ) from e


async def _authorize_session_access(
    session: dict,
    current_user: UserResponse | None,
    x_session_token: str | None,
    customer_repo: CustomerRepository,
) -> bool:
    """
    Validates if caller has legitimate authority to inspect or close a conversation session:
    1. Dispatcher or Admin user roles
    2. Authenticated Customer owning the session
    3. Caller presenting valid capability X-Session-Token
    """
    if current_user:
        if current_user.role in (UserRole.ADMIN, UserRole.DISPATCHER):
            return True
        if current_user.role == UserRole.CUSTOMER:
            cust = await customer_repo.get_by_user_id(current_user.id)
            if cust and session.get("customer_id") == cust["id"]:
                return True
            if session.get("customer_id") == current_user.id:
                return True

    session_token = session.get("session_token")
    if session_token and x_session_token:
        if secrets.compare_digest(x_session_token, session_token):
            return True

    return False


@router.get(
    "/sessions/{session_id}",
    response_model=ConversationSessionRead,
    status_code=status.HTTP_200_OK,
    summary="Retrieve session state, bounded history, and work-order extraction draft",
)
async def get_session_state(
    session_id: str,
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    current_user: UserResponse | None = Depends(get_current_user_optional),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    customer_repo: CustomerRepository = Depends(get_customer_repo),
) -> ConversationSessionRead:
    session = await conversation_repo.get_by_session_id(session_id)
    if not session:
        raise EntityNotFoundException("ConversationSession", session_id)

    is_authorized = await _authorize_session_access(
        session, current_user, x_session_token, customer_repo
    )
    if not is_authorized:
        if not current_user and not x_session_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials or X-Session-Token header required.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this session.",
        )

    return ConversationSessionRead(**session)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Close and terminate an active intake conversation session",
)
async def close_session(
    session_id: str,
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    current_user: UserResponse | None = Depends(get_current_user_optional),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    customer_repo: CustomerRepository = Depends(get_customer_repo),
):
    session = await conversation_repo.get_by_session_id(session_id)
    if not session:
        raise EntityNotFoundException("ConversationSession", session_id)

    is_authorized = await _authorize_session_access(
        session, current_user, x_session_token, customer_repo
    )
    if not is_authorized:
        if not current_user and not x_session_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials or X-Session-Token header required.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to close this session.",
        )

    await conversation_repo.update_session_state(session_id, {"status": "closed"})
    return {"message": "Session closed successfully", "session_id": session_id}
