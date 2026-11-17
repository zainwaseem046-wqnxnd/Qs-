from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    DB,
    REFRESH_COOKIE,
    CurrentUser,
    client_ip,
)
from app.core.config import get_settings
from app.core.db import set_rls_context
from app.core.errors import NotAuthenticated
from app.core.ratelimit import check_rate_limit
from app.core.security import generate_token
from app.domains.audit.service import AuditActor
from app.domains.identity import service
from app.domains.identity.models import User
from app.domains.identity.schemas import (
    AcceptInvitationRequest,
    ChangePasswordRequest,
    InvitationPreview,
    LoginRequest,
    LoginResult,
    MembershipSummary,
    MfaCodeRequest,
    MfaDisableRequest,
    MfaSetupOut,
    MfaVerifyRequest,
    PasswordConfirmRequest,
    RegisterRequest,
    SessionOut,
    UpdateProfileRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_PATH = "/api/v1/auth"


def _meta(request: Request) -> AuditActor:
    return AuditActor(None, None, client_ip(request), request.headers.get("user-agent"),
                      request.headers.get("x-request-id"))


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    common = {"secure": s.cookie_secure, "samesite": "lax"}
    response.set_cookie(ACCESS_COOKIE, access, max_age=s.access_token_ttl_seconds, httponly=True, path="/", **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_ttl_seconds, httponly=True,
                        path=REFRESH_PATH, **common)
    # Double-submit CSRF token: readable by the SPA, echoed in the X-CSRF-Token header.
    response.set_cookie(CSRF_COOKIE, generate_token(24), max_age=s.refresh_token_ttl_seconds, httponly=False,
                        path="/", **common)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")


def session_out(db: Session, user: User) -> SessionOut:
    memberships = [
        MembershipSummary(
            tenant_id=t.id, tenant_name=t.name, tenant_slug=t.slug,
            role_key=r.key if r else None, role_name=r.name if r else None,
        )
        for _m, t, r in service.memberships_for_user(db, user.id)
    ]
    return SessionOut(user=UserOut.model_validate(user), memberships=memberships)


def _sign_in(db: Session, request: Request, response: Response, user: User) -> LoginResult:
    meta = _meta(request)
    service.complete_login(db, user, meta)
    refresh = service.create_session(db, user, user_agent=meta.user_agent, ip=meta.ip_address)
    access = service.create_access_token(user)
    result = LoginResult(session=session_out(db, user), access_token=access)
    db.commit()
    _set_auth_cookies(response, access, refresh)
    return result


@router.post("/register", response_model=LoginResult, status_code=201)
def register(body: RegisterRequest, request: Request, response: Response, db: DB) -> LoginResult:
    check_rate_limit("register", client_ip(request) or "unknown", 5)
    result = service.register_organization(
        db, full_name=body.full_name, email=body.email, password=body.password,
        organization_name=body.organization_name, home_state=body.home_state, meta=_meta(request),
    )
    return _sign_in(db, request, response, result.user)


@router.post("/login", response_model=LoginResult)
def login(body: LoginRequest, request: Request, response: Response, db: DB) -> LoginResult:
    limit = get_settings().login_rate_limit_per_minute
    check_rate_limit("login-ip", client_ip(request) or "unknown", limit * 3)
    check_rate_limit("login-email", body.email.lower(), limit)
    try:
        user = service.authenticate(db, body.email, body.password, _meta(request))
    except NotAuthenticated:
        db.commit()  # persist the failed-attempt audit event
        raise
    if user.mfa_enabled:
        db.commit()
        return LoginResult(mfa_required=True, mfa_token=service.create_mfa_challenge(user))
    return _sign_in(db, request, response, user)


@router.post("/mfa/verify", response_model=LoginResult)
def mfa_verify(body: MfaVerifyRequest, request: Request, response: Response, db: DB) -> LoginResult:
    user = service.user_from_mfa_challenge(db, body.mfa_token)
    check_rate_limit("mfa", str(user.id), 5)
    if not service.verify_mfa_code(user, body.code):
        raise NotAuthenticated("Invalid verification code", code="invalid_code")
    return _sign_in(db, request, response, user)


@router.post("/refresh", response_model=LoginResult)
def refresh(request: Request, response: Response, db: DB) -> LoginResult:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise NotAuthenticated("Session expired. Please sign in again.", code="refresh_invalid")
    meta = _meta(request)
    try:
        user, new_refresh = service.rotate_refresh_token(db, token, user_agent=meta.user_agent, ip=meta.ip_address)
    except service.RefreshReuseDetected:
        db.commit()
        _clear_auth_cookies(response)
        raise
    access = service.create_access_token(user)
    result = LoginResult(session=session_out(db, user), access_token=access)
    db.commit()
    _set_auth_cookies(response, access, new_refresh)
    return result


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB) -> Response:
    service.logout(db, request.cookies.get(REFRESH_COOKIE))
    db.commit()
    response.status_code = 204
    _clear_auth_cookies(response)
    return response


@router.get("/me", response_model=SessionOut)
def me(uctx: CurrentUser, db: DB) -> SessionOut:
    return session_out(db, uctx.user)


@router.patch("/me", response_model=UserOut)
def update_profile(body: UpdateProfileRequest, uctx: CurrentUser, db: DB) -> UserOut:
    uctx.user.full_name = body.full_name
    db.commit()
    return UserOut.model_validate(uctx.user)


@router.post("/password", status_code=204)
def change_password(body: ChangePasswordRequest, uctx: CurrentUser, response: Response, db: DB) -> Response:
    service.change_password(db, uctx.user, body.current_password, body.new_password, uctx.actor())
    db.commit()
    _clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.post("/mfa/setup", response_model=MfaSetupOut)
def mfa_setup(body: PasswordConfirmRequest, uctx: CurrentUser, db: DB) -> MfaSetupOut:
    check_rate_limit("mfa-setup", str(uctx.user.id), 5)
    secret, uri = service.start_mfa_setup(uctx.user, body.password)
    db.commit()
    return MfaSetupOut(secret=secret, otpauth_uri=uri)


@router.post("/mfa/enable", response_model=UserOut)
def mfa_enable(body: MfaCodeRequest, uctx: CurrentUser, db: DB) -> UserOut:
    check_rate_limit("mfa", str(uctx.user.id), 5)
    service.enable_mfa(db, uctx.user, body.code, uctx.actor())
    db.commit()
    return UserOut.model_validate(uctx.user)


@router.post("/mfa/disable", response_model=UserOut)
def mfa_disable(body: MfaDisableRequest, uctx: CurrentUser, db: DB) -> UserOut:
    check_rate_limit("mfa", str(uctx.user.id), 5)
    service.disable_mfa(db, uctx.user, body.password, body.code, uctx.actor())
    db.commit()
    return UserOut.model_validate(uctx.user)


@router.get("/invitations/{token}", response_model=InvitationPreview)
def invitation_preview(token: str, request: Request, db: DB) -> InvitationPreview:
    check_rate_limit("invite", client_ip(request) or "unknown", 30)
    found = service.lookup_invitation(db, token)
    return InvitationPreview(
        email=found.invitation.email, tenant_name=found.tenant.name, role_name=found.role.name,
        expires_at=found.invitation.expires_at, account_exists=found.existing_user is not None,
    )


@router.post("/invitations/{token}/accept", response_model=LoginResult)
def invitation_accept(
    token: str, body: AcceptInvitationRequest, request: Request, response: Response, db: DB
) -> LoginResult:
    check_rate_limit("invite", client_ip(request) or "unknown", 30)
    user, created = service.accept_invitation(
        db, token, full_name=body.full_name, password=body.password, meta=_meta(request)
    )
    if created:
        set_rls_context(db, user_id=user.id)
        return _sign_in(db, request, response, user)
    # Existing accounts sign in normally afterwards (so MFA is always enforced).
    db.commit()
    return LoginResult()
