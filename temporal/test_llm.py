import asyncio

from temporal.llm_client import ask_llm


async def main():

    response = await ask_llm(
        "What is Kubernetes?"
    )

    print(response)


if __name__ == "__main__":
    asyncio.run(main())