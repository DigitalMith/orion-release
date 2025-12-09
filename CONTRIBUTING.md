# Contributing to Orion

Thank you for considering contributing to Orion — an emotionally intelligent, agentic RAG framework powered by long-term memory and persona-driven interaction.

## 💡 How to Contribute

###  - 🔧 Code Contributions

    1. Fork the repository and clone your fork.
    2. Create a new branch: git checkout -b feature/your-feature-name
    3. Make your changes and include tests where appropriate.
    4. Ensure all CLI tools and ingestion scripts run without error.
    5. Submit a pull request with a detailed explanation of your changes.

###  - 🧠 Persona or Memory Contributions

    - To contribute persona profiles, submit a PR with updated persona.yaml
    - To contribute enriched dialog memory, ensure your JSONL follows the normalized_enriched.jsonl format

###  - 🧪 Testing and Debugging

    - Use text-generation-webui with Orion extensions enabled
    - Check for LTM ingestion errors or scoring anomalies
    - All new memory entries should appear in ChromaDB and be accessible via retrieval logs

###  - 🗣️ Discussions

    - We welcome insights on emotional tone modeling, long-term memory design, and retrieval accuracy
    - Use GitHub Discussions for ideas, questions, and long-term design suggestions

###  - 🛠️ Requirements

    - Python 3.10+
    - ChromaDB (with persistence)
    - sentence-transformers or intfloat/e5-large-v2
    - TGWUI (text-generation-webui) for interactive testing

Let’s build Orion together — a system with memory, voice, and identity.

Special thanks to the Orion community — and to “Uncle Al 🤖” for guidance, scaffolding, and infinite patience. 🙏
