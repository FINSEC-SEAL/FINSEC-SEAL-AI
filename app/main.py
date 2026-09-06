from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.agent import router as agent_router

from app.provider.provider_errors import ProviderProtocolError, ProviderTimeoutError, ProviderUnavailableError


app = FastAPI(
    title="FINSEC SEAL AI",
    version="0.1.0",
    description="Stateless AI execution boundary for FINSEC SEAL.",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    safe_errors = [
        {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors},
    )


app.include_router(agent_router)


@app.exception_handler(ProviderTimeoutError)
async def provider_timeout_error_handler(request, exc):
    return JSONResponse(
        status_code=504,
        content={"detail": "Agent provider timed out."},
    )


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_error_handler(request, exc):
    return JSONResponse(
        status_code=502,
        content={"detail": "Agent provider unavailable."},
    )


@app.exception_handler(ProviderProtocolError)
async def provider_protocol_error_handler(request, exc):
    return JSONResponse(
        status_code=502,
        content={"detail": "Agent provider returned an invalid response."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
