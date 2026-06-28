# watchtowerV2

Streamlit app for multi-sensor environmental intelligence using satellite imagery, NASA FIRMS data, and Cerebras-hosted agent analysis.

## Local setup

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Add secrets locally using one of these options:

   - Preferred Streamlit format: copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill in real values.
   - Local-only `.env` fallback:

     ```bash
     CERBRAS_API_KEY=your_cerebras_key
     FIRMS_API_KEY=your_firms_key
     ```

4. Run the app:

   ```bash
   streamlit run main.py
   ```

## Required secrets

- `CERBRAS_API_KEY` — Cerebras Cloud API key.
- `FIRMS_API_KEY` — NASA FIRMS API key.

Do not commit `.env` or `.streamlit/secrets.toml`; both are ignored by Git.

## Streamlit Community Cloud deployment

1. Push this repo to GitHub.
2. Open Streamlit Community Cloud and create a new app from this repository.
3. Set the app entrypoint to `main.py`.
4. Add the required secrets in the app settings using the names above.
5. Deploy and verify the app loads without a missing-secret error.
