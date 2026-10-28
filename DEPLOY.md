# Deploying Exhibit A (optional)

The simplest "working demo" is local: `python -m exhibit_a serve` and click **Replay demo**.
If you want a hosted URL for the submission, here are two easy options.

## Option A — any container host (Render, Railway, Fly.io, a VM)
```bash
docker build -t exhibit-a -f app.Dockerfile .
docker run -p 8000:8000 --env-file .env exhibit-a
```
The UI is served at `/`. For a public demo you can run in **replay mode** (no key) by leaving
`NEBIUS_API_KEY` empty — visitors can click **Replay demo** and see the recorded run safely,
with no live scanning of arbitrary repos.

## Option B — a quick public tunnel for the video
```bash
python -m exhibit_a serve
# in another shell:
ngrok http 8000      # or cloudflared tunnel --url http://localhost:8000
```

## Security note
If you expose live scanning publicly, only point it at repos you control, and keep the Docker
sandbox enabled (`EXHIBIT_SANDBOX=docker`). For a public demo, replay mode is the safe default.
