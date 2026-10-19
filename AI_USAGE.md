# AI Coding Tools Disclosure

AI coding assistance was used to help break down the challenge requirements, draft parts of the implementation, and suggest documentation and test cases. I reviewed the implementation, ran it locally, and checked the main application flows.

## AI Models Used by the Application

The application uses locally hosted Ollama models:

- **Embedding model:** `nomic-embed-text`
- **Language model:** `llama3.2:3b`

The application generates embeddings for document chunks, retrieves relevant chunks for a user's question, and uses the retrieved context to generate an answer with source references. The local setup does not require a paid OpenAI API key.

## Design Choices and Trade-offs

I chose local models so the demo can run without paid API credentials. This makes the setup accessible, but performance and answer quality depend on the available hardware, the documents provided, and the selected models.

The current implementation is a demonstration, not a production-ready knowledge platform. Production use would require evaluation of retrieval and answer quality, stronger access controls, monitoring, suitable data-retention policies, and load testing.

## Responsibility and Verification

AI coding assistance does not replace testing or review. I am responsible for understanding the code, verifying its behavior, explaining the design decisions, and addressing issues identified during testing.

## Example of a Reviewed AI Suggestion

One suggestion was to use a hosted embedding and language model provider. I chose local Ollama models instead, using `nomic-embed-text` for embeddings and `llama3.2:3b` for answer generation, so the application can run without paid API credentials. I documented this trade-off and verified the local application flow.