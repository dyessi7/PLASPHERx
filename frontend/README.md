# SPHEREx Sky Viewer — frontend

React + Vite single-page app. Enter sky coordinates (RA/Dec) and watch the
SPHEREx images of that spot as a short animation, to spot things that move or
change brightness. All data comes live from the project API.

## Run locally

Requires Node.js 20 or newer.

```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173).

Production build:

```bash
npm run build     # output in dist/
npm run preview   # serve the build locally
```

## Configuration

| Variable       | Required | Description                                                      |
| -------------- | -------- | ---------------------------------------------------------------- |
| `VITE_API_URL` | yes      | Base URL of the API, without a trailing slash. Read at build time. |

If `VITE_API_URL` is not set, the app still loads and shows
"The data service is not configured."

## API endpoints used

| Endpoint | When |
| --- | --- |
| `GET /api/frames?ra=&dec=&fov=&detector=&n=16` | Every search. Each frame `url` is then downloaded individually. |
| `GET /api/epochs?ra=&dec=&fov=&detector=&n=16` | After all frames finished loading. Epoch and difference images are data URIs. |
| `GET /api/spectrum?ra=&dec=&fov=&detector=D1..D6&n=4` | When the user clicks "Build spectrum"; one call per detector, two at a time. |

- If `/api/epochs` or `/api/spectrum` answer 404 or 501, the matching tab is hidden.
- Frame PNGs may include an `X-Wavelength-Um` response header; it is shown next
  to the date. Because the API is on another origin, the server must send
  `Access-Control-Expose-Headers: X-Wavelength-Um` for the browser to read it.
- Errors are expected as JSON `{"error": "..."}` with a 4xx/5xx status.

## Shareable URLs

The current search is kept in the page URL:

```
?ra=248.1675&dec=66.755&fov=0.1&detector=D2
```

Opening such a link runs that search directly.

## Keyboard shortcuts

- Space: play / pause
- Left / Right arrows: previous / next frame

## Project layout

```
src/
├── api.js              API calls (frames, frame images, epochs, spectrum)
├── constants.js        detectors, colors, suggested targets, field limits
├── query.js            form validation and URL sync
├── App.jsx             page layout, search state, tabs
├── hooks/              useLiveFrames, useEpochs, useSpectrum
├── components/         SearchForm, TargetButtons, DetectorSelect, Player,
│                       EpochView, SpectrumChart
└── styles/             plain CSS, dark theme
```
