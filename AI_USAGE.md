# AI coding tools disclosure

AI coding assistance was used to help break down the challenge requirements, draft parts of the implementation, and suggest documentation and test cases. I am responsible for reviewing the implementation, running it locally, and being able to explain the design and trade-offs.

The submitted demo uses TF-IDF vectors and an extractive answer fallback so it can run without API credentials or paid model calls. This is explicitly described as an offline substitute; it is not presented as a neural embedding model or an LLM. Before extending this project for production, the retrieval and answer-generation adapters should be replaced with provider-backed implementations and tested against a representative evaluation set.

## Example of a design choice I reviewed

A provider-backed embedding and LLM flow is closer to production RAG, but would make the first run depend on credentials, network access, and provider availability. I chose an offline retrieval and extractive-answer fallback for reproducibility and documented the boundary where real embedding and LLM services can be integrated. The trade-off is that lexical TF-IDF retrieval is less capable than neural semantic retrieval, and the extractive answer is not free-form LLM generation.
