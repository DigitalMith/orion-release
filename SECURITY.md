# Security Policy

## Supported Versions

Only the latest stable version of Orion (currently v3.45.0) receives active security updates. Previous versions are not maintained unless critical vulnerabilities are discovered.

## Reporting a Vulnerability

If you discover a security vulnerability in Orion:

  1. **Do not open a public issue.**
  2. Email the maintainer directly at: `jrichards00@proton.me`
  3. Include:

    - A description of the vulnerability
    - Steps to reproduce
    = Potential impact and scope
    - Suggestions or mitigation if possible

You will receive a response within 72 hours.

## 🔐 Security Considerations

  - Orion uses ChromaDB and local JSONL data — no external API transmissions unless explicitly enabled
  - All inference is performed locally
  - No user data is transmitted unless configured otherwise by the user

## 👥 Coordinated Disclosure

We follow Coordinated Vulnerability Disclosure (CVD) and will work with reporters to responsibly publish findings if necessary.

## 🧠 Model Safety

This project embeds conversational memory and personalization features. Developers and users are responsible for monitoring outputs and ensuring safe, ethical use.

If you are unsure whether an issue is security-related, err on the side of private disclosure.