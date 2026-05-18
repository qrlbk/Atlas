from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.imports import router as imports_router
from app.api.resources import router as resources_router
from app.api.product import router as product_router
from app.api.solver_jobs import router as solver_jobs_router
from app.api.suggestions import router as suggestions_router
from app.api.validation import router as validation_router
from app.core.config import resolved_cors_origins
from app.i18n import resolve_locale, t


app = FastAPI(title="Atlas API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=resolved_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(resources_router)
app.include_router(validation_router)
app.include_router(analytics_router)
app.include_router(suggestions_router)
app.include_router(imports_router)
app.include_router(solver_jobs_router)
app.include_router(product_router)


@app.middleware("http")
async def locale_middleware(request: Request, call_next):
    locale = resolve_locale(request)
    request.state.locale = locale
    response = await call_next(request)
    response.headers["Content-Language"] = locale
    return response


@app.exception_handler(HTTPException)
async def localized_http_exception_handler(request: Request, exc: HTTPException):
    locale = getattr(request.state, "locale", "en")
    detail = exc.detail
    if isinstance(detail, dict) and "key" in detail:
        key = str(detail["key"])
        params = detail.get("params", {}) if isinstance(detail.get("params"), dict) else {}
        message = t(locale, key, **params)
        payload = {"detail": message, "code": key}
    elif isinstance(detail, str):
        payload = {"detail": detail}
    else:
        payload = {"detail": t(locale, "errors.requestValidation")}
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def localized_request_validation_handler(request: Request, exc: RequestValidationError):
    locale = getattr(request.state, "locale", "en")
    return JSONResponse(
        status_code=422,
        content={"detail": t(locale, "errors.requestValidation"), "errors": exc.errors(), "code": "errors.requestValidation"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
