from app.schemas.llm import GenerateRequest, GenerateResponse, ModelsResponse
from fastapi import APIRouter
from app.core.llm.factory import get_llm_provider

router = APIRouter()


@router.post(
    "/test/generate",
    response_model=GenerateResponse,
    summary="Generate LLM response",
    description="Generate a response using the configured LLM provider.",
)
async def test_generate(request: GenerateRequest):
    provider = get_llm_provider()
    response = await provider.generate(request.prompt, request.system)
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
    models = await provider.list_models()
    return ModelsResponse(
        provider=type(provider).__name__,
        models=models,
    )
