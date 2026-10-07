# Contributing to Voice Agent

## Development

Use Python 3.11+ and uv. Tests and preview do not require an API key. Tests import the audio pipeline, so install the PortAudio runtime first (`sudo apt-get install libportaudio2` on Ubuntu/Debian; `brew install portaudio` on macOS).

```sh
uv sync --locked
uv run pytest tests/ -q
uv build
uv run voice-agent --demo --web --no-open
```

Preserve audio sample contracts, thread/async boundaries, cooperative cancellation, and immediate playback stop. Add focused regression tests for behavior changes. Verify a real microphone/speaker conversation separately when changing the audio pipeline; preview metrics are synthetic.

## Screenshots

Capture the running `--demo --web` companion and label the image as preview. Never use personal transcripts or keys. Mode badges must describe the selected backend accurately. Static web assets ship in the Python wheel; verify packaging when changing their paths.

## Documentation site

The public site is https://natelindev-voice-agent.pages.dev/. Its Cloudflare Pages project is `natelindev-voice-agent`. Current deployments use manual Direct Upload; automatic Cloudflare deployments are not configured.

Edit `docs/` and check desktop/mobile layouts, navigation, code copying, images, and light/dark appearance. The static HTML remains readable without JavaScript. Preview with `python3 -m http.server 8000 --directory docs`.

To publish, authenticate Wrangler to the account owning the project with Pages write permission:

```sh
npx --yes wrangler@4.148.0 login
npx --yes wrangler@4.148.0 pages deploy docs --project-name natelindev-voice-agent --branch main
```

Alternatively, upload a ZIP of the contents of `docs/` in the project dashboard, with `index.html` at the archive root. The included `deploy-docs.yml` workflow can publish using repository secrets `CLOUDFLARE_API_TOKEN` (Account → Cloudflare Pages → Edit) and `CLOUDFLARE_ACCOUNT_ID`. These secrets are not currently configured. See [Cloudflare’s direct-upload CI guide](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).

## Pull requests and reports

Describe the user-visible change and relevant verification. Keep private keys, API tokens, personal transcripts, and private hostnames out of commits, screenshots, and reports. Include a small reproduction and OS/tool versions. Brand assets live in `docs/assets/brand/`; marks are path-based SVGs, with transparent PNG exports and dark variants.
