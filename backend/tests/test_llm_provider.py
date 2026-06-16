import pytest


@pytest.mark.asyncio
async def test_echo_generate(llm_provider):
    response = await llm_provider.generate("Hello")
    assert "Hello" in response
    assert response.startswith("[Echo]")


@pytest.mark.asyncio
async def test_echo_generate_with_system(llm_provider):
    response = await llm_provider.generate(
        "Hello",
        system="You are a helpful assistant",
    )
    assert "Hello" in response
    assert response.startswith("[Echo - system:")


@pytest.mark.asyncio
async def test_echo_list_models(llm_provider):
    models = await llm_provider.list_models()
    assert "echo" in models
