
from app.core.llm.factory import get_llm_provider
from app.core.logging import logger
from app.schemas.llm import GenerateRequest, GenerateResponse, ModelsResponse
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post(
    "/test/generate",
    response_model=GenerateResponse,
    summary="Generate LLM response",
    description="Generate a response using the configured LLM provider.",
)
async def test_generate(request: GenerateRequest):
    provider = get_llm_provider()
    logger.info(
        "Generate request: provider=%s prompt_len=%d",
        type(provider).__name__,
        len(request.prompt),
    )
    try:
        response = await provider.generate(request.prompt, request.system)
    except TimeoutError:
        logger.error(
            "LLM generation timed out for provider=%s", type(provider).__name__
        )
        raise HTTPException(status_code=504, detail="LLM generation timed out")
    logger.info(
        "Generate success: provider=%s response_len=%d",
        type(provider).__name__,
        len(response),
    )
    return GenerateResponse(
        provider=type(provider).__name__,
        response=response,
    )


@router.get(
    "/test/models",
    response_model=ModelsResponse,
    summary="List available models",
    description="List models available from the active LLM provider.",
)
async def list_models():
    provider = get_llm_provider()
    logger.info("List models request: provider=%s", type(provider).__name__)
    try:
        models = await provider.list_models()
    except TimeoutError:
        logger.error(
            "LLM model listing timed out for provider=%s", type(provider).__name__
        )
        raise HTTPException(status_code=504, detail="LLM model listing timed out")
    logger.info(
        "List models success: provider=%s count=%d",
        type(provider).__name__,
        len(models),
    )
    return ModelsResponse(
        provider=type(provider).__name__,
        models=models,
    )
